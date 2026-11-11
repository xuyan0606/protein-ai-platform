"""User-authored protein text parsers shared by intake and orchestration."""
import re
from app.services.property_workflow_governance import PropertyWorkflowRouter


def strip_attachment_metadata(text: str) -> str:
    """Remove file metadata blocks before parsing user residue/mutation text."""
    if not isinstance(text, str):
        return ""
    # Browser attachments can share a line with the actual user request.
    # Remove the balanced metadata block while preserving the user prefix.
    parts = []
    cursor = 0
    marker = re.compile(r"\[Attached files:", re.I)
    while match := marker.search(text, cursor):
        parts.append(text[cursor:match.start()])
        depth, quoted, escaped = 1, False, False
        end = match.end()
        while end < len(text) and depth:
            char = text[end]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
            end += 1
        cursor = end
    parts.append(text[cursor:])
    text = "".join(parts)
    cleaned_lines: list[str] = []
    skip_attachment_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if lower.startswith("[attached files") or lower.startswith("attached files"):
            skip_attachment_block = True
            continue
        if skip_attachment_block:
            if "]" in line:
                skip_attachment_block = False
            continue
        if any(key in lower for key in ("object_name", "download_url", "/api/files/", "uploads/")):
            continue
        cleaned_lines.append(raw_line)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"/\S+", " ", cleaned)
    return cleaned


def extract_sequence(text: str) -> str | None:
    """Extract a valid amino-acid sequence from FASTA, labelled, or raw sequence text.

    The raw fallback is intentionally case-sensitive. Otherwise ordinary words such
    as "specificity" are valid one-letter amino-acid strings and get misread as
    short protein fragments in mixed Chinese/English prompts.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    def _clean(candidate: str) -> str:
        return re.sub(r"[^ACDEFGHIKLMNPQRSTVWY]", "", candidate.upper())

    fasta_blocks = re.findall(r">[^\n\r]*(?:\r?\n)([A-Za-z\s\r\n-]{10,})", text)
    fasta_matches = [_clean(block) for block in fasta_blocks]
    fasta_matches = [seq for seq in fasta_matches if len(seq) >= 10]
    if fasta_matches:
        return max(fasta_matches, key=len)

    labelled_matches = re.findall(
        r"(?:序列|氨基酸序列|protein sequence|sequence)\s*(?:为|是|=|[:：])\s*([A-Za-z\s\r\n-]{10,})",
        text,
        re.IGNORECASE,
    )
    labelled = [_clean(match) for match in labelled_matches]
    labelled = [seq for seq in labelled if len(seq) >= 10]
    if labelled:
        return max(labelled, key=len)

    sanitized = re.sub(r"序列前缀\s*[`=:：-]*\s*[ACDEFGHIKLMNPQRSTVWY]{10,}\s*`?", " ", text)
    sanitized = re.sub(r"sequence preview\s*[`=:：-]*\s*[ACDEFGHIKLMNPQRSTVWY]{10,}\s*`?", " ", sanitized, flags=re.IGNORECASE)
    matches = re.findall(r'(?<![A-Za-z])[ACDEFGHIKLMNPQRSTVWY]{10,}(?![A-Za-z])', sanitized)
    if matches:
        return max(matches, key=len).upper()
    return None


def user_task_text(text: str) -> str:
    """Ignore metadata and context labels when interpreting a user's intent."""
    value = re.sub(r"\[(?:Prior [^\]]*|Uploaded structure[^\]]*|Context boundary[^\]]*)\]", "", str(text or ""), flags=re.I)
    # Inline attachment records can share a line with the actual request.
    value = re.sub(r"Attachment\s+\d+\s*\([^)]*\)", "", value, flags=re.I)
    return strip_attachment_metadata(value)


def explicit_new_task(text: str) -> bool:
    value = user_task_text(text)
    # Negated reset requests describe continuity, not a task boundary. Strip
    # just the negated phrase, so a later positive reset still takes effect.
    value = re.sub(
        r"(?:不是|并非|并不是|不算|不要|别|不用|无需)\s*"
        r"(?:(?:再|重新|另外)\s*)?(?:开|开始|启动|建|创建)?\s*(?:一个|个)?\s*"
        r"(?:新的?\s*(?:任务|对话)|重新开(?:任务|对话)?)", "", value)
    # A method/tool change acts on the current object. Its grammatical object
    # must not be confused with changing the enzyme or explicitly resetting.
    value = re.sub(r'(?:另一个|另一条|换一个|换个|换条)\s*(?:新的?)?\s*'
                   r'(?:策略|流程|方法|工具|模型|算法|评分|参数|路线|报告|表格|建议|方案)', '', value)
    value = re.sub(r'(?:触发|识别为|判定为|当作|认为是)\s*(?:新的?)?任务', '', value)
    value = re.sub(r'(?:什么是|何为)\s*新任务|新任务(?:是什么|是什么意思|的关键词)', '', value)
    return bool(re.search(
        r"重新开|新任务|新对话|新的对话|另一条|另一个|换一个|换个|换条|不同序列|不要接着|不是上面|"
        r"another sequence|different sequence|new task|new conversation|start over", value, re.I
    ))


def reanalyze_current(text: str) -> bool:
    return not explicit_new_task(text) and bool(re.search(
        r"(?:重新|再次|再)\s*(?:分析|评估|检查|审计|复核).{0,12}(?:刚才|上面|这个|当前|该).{0,8}"
        r"(?:蛋白|序列|结构|酶|PDB|文件|对象|样品)", user_task_text(text), re.I
    ))


def continuation_request(text: str) -> bool:
    value = user_task_text(text).strip()
    if not value or explicit_new_task(value):
        return False
    if re.search(r'(?:另一个|另一条|换一个|换个|换条)\s*(?:新的?)?\s*'
                 r'(?:策略|流程|方法|工具|模型|算法|评分|参数|路线|报告|表格|建议|方案)', value):
        return True
    if re.search(r'(?:不要|不用|无需|别)\s*(?:重新)?(?:开|启动|重启)(?:流程|任务|对话)', value):
        return True
    return reanalyze_current(value) or bool(re.search(r'沿用(?:原|上)|接着(?:原|上)|上一个项目', value)) or bool(re.match(
        r"^(?:继续|接着|进一步)(?:深度)?(?:分析|解决|修复|检查|审计|打磨|优化|处理)?"
        r"|^(?:深度分析|再说人话|再说|这个什么意思|什么意思|展开|详细说说)", value, re.I
    ))


def task_sequence(text: str) -> str | None:
    return extract_sequence(user_task_text(text))


def requested_candidate_count(text: str) -> int | None:
    """Read a user's output budget, including modifiers and later count edits.

    Keep this shared by history recovery and first-turn planning. File metadata,
    assay temperatures and durations must never supply a candidate budget.
    """
    value = user_task_text(text)
    # A complaint about an old report is not a replacement quantity request.
    value = '。'.join(clause for clause in re.split(r'[。！？\n]', value)
                     if not re.search(r'为什么|为何|怎么|是否|已经|做过|返回了|输出了', clause))
    patterns = (
        r'(?P<count>\d+)\s*个?\s*(?:突变位点|突变|候选|位点)',
        r'(?:输出|给出|提供|列出|生成|筛选|返回)[^。！？\n]{0,24}?(?P<count>\d+)\s*个[^。！？\n]{0,24}(?:突变|替换|候选|位点)',
        r'(?:只要|只需|数量(?:改为|改成|为|是|[:：])|改为|改成)\s*(?P<count>\d+)\s*个',
        r'(?:output|return|provide|generate|select)\s+(?P<count>\d+)\s+(?:specific\s+)?(?:mutations?|substitutions?|candidates?|sites?)',
    )
    matches = [m for pattern in patterns for m in re.finditer(pattern, value, re.I)]
    if not matches:
        saved = re.search(r'\[Prior candidate request: 输出(\d+)个突变位点', str(text or ''))
        return int(saved[1]) if saved and 1 <= int(saved[1]) <= 384 else None
    # A later explicit edit in the same utterance replaces the earlier budget.
    count = int(max(matches, key=lambda m: m.start('count'))['count'])
    return count if 1 <= count <= 384 else None


def structure_objects(text: str) -> tuple[str, ...]:
    candidates = re.findall(r"['\"]?object_name['\"]?\s*[:=]\s*['\"]?([^'\"\s,\]\})]+)", str(text or ""))
    return tuple(dict.fromkeys(c for c in candidates if c.startswith("uploads/") and "[" not in c))


def protein_reference(text: str) -> str:
    value = user_task_text(text)
    match = re.search(r"\bpdb\s*(?:id|编号|号)?\s*[:：=]?\s*([0-9][A-Za-z0-9]{3})\b", value, re.I)
    if not match:
        match = next((m for m in re.finditer(r"\b([0-9][A-Za-z0-9]{3})\b", value)
                      if not re.fullmatch(r'\d(?:min|hrs|sec|mms|nms)', m[1], re.I)), None)
    if match:
        return "pdb:" + match.group(1).upper()
    match = re.search(r"\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z0-9]{3}[0-9])\b", value, re.I)
    return "accession:" + match.group(0).upper() if match else ""


def task_goal_summary(route: dict, source_text: str = "") -> str:
    labels = {"activity": "比活力", "stability": "稳定性", "ph": "pH 适应性",
              "expression": "表达量", "specificity": "特异性"}
    if re.search(r"热稳定|耐热|thermal", user_task_text(source_text), re.I):
        labels["stability"] = "热稳定性"
    constraints = {"activity_not_drop": "活性不能下降", "stability_not_drop": "稳定性不能下降",
                   "expression_not_drop": "表达量不能下降", "specificity_not_drop": "特异性不能下降"}
    goal = "提高" + "和".join(labels.get(k, k) for k in route.get("optimization_targets", []))
    return "，".join([goal, *[constraints[k] for k in route.get("preservation_constraints", []) if k in constraints]])


def active_task_history(history: list[dict] | None) -> list[dict]:
    """Cut history at explicit task and changed sequence/reference boundaries.

    Upload replacement keeps the goal available to intake; orchestration must
    retain only the current upload when constructing concrete tool context.
    """
    scoped: list[dict] = []
    last_sequence = None
    last_reference = ""
    last_objects = ()
    for item in history or []:
        if not isinstance(item, dict):
            continue
        if item.get("role") == "user":
            text = str(item.get("content") or "")
            sequence = task_sequence(text)
            reference = protein_reference(text)
            if explicit_new_task(text) or (sequence and last_sequence and sequence != last_sequence) or (reference and last_reference and reference != last_reference):
                scoped = []
                last_sequence = None
                last_reference = ""
                last_objects = ()
            objects = structure_objects(text)
            if objects and ((last_objects and set(objects) != set(last_objects)) or (last_sequence and not last_objects)):
                route = PropertyWorkflowRouter.route(user_task_text(text))
                previous_goal_text = next((str(row.get("content") or "")
                                           for row in reversed(scoped) if row.get("role") == "user"
                                           and PropertyWorkflowRouter.route(user_task_text(str(row.get("content") or ""))).get("workflow_id")), "")
                previous_goal = PropertyWorkflowRouter.route(user_task_text(previous_goal_text))
                scoped = ([{"role": "user", "content": task_goal_summary(previous_goal, previous_goal_text)}]
                          if previous_goal.get("workflow_id") and not route.get("optimization_targets") else [])
            if objects:
                # An upload supplies the current object, never its predecessor's
                # FASTA or reference. Its goal can still be an input update.
                last_sequence = None
                last_reference = ""
                last_objects = objects
            last_sequence = sequence or last_sequence
            last_reference = reference or last_reference
        scoped.append(item)
    return scoped


def task_memory_for_reply(history: list[dict], recent_limit: int = 4) -> list[dict]:
    """Pin user-authored task facts alongside recent turns, within one task.

    Keep original text as user data rather than inventing an LLM summary or
    promoting assistant guesses to durable identity/experimental evidence.
    """
    scoped = active_task_history(history)
    recent_start = max(0, len(scoped) - recent_limit)
    user_indices = [i for i, row in enumerate(scoped) if row.get('role') == 'user']
    anchors = [i for i in user_indices if (
        task_sequence(str(scoped[i].get('content') or ''))
        or structure_objects(str(scoped[i].get('content') or ''))
        or protein_reference(str(scoped[i].get('content') or ''))
        or re.search(r'项目|目标|条件|测定|底物|缓冲|残余|℃|分钟|不要|禁止|仅本地|限制|保护|链|project|objective|assay|buffer',
                     user_task_text(str(scoped[i].get('content') or '')), re.I)
        or PropertyWorkflowRouter.route(user_task_text(str(scoped[i].get('content') or ''))).get('optimization_targets')
    )]
    pinned = set(anchors[-12:])
    if user_indices:
        pinned.add(user_indices[0])
    return [row for i, row in enumerate(scoped) if i in pinned or i >= recent_start]
