// navigator.clipboard only exists in secure contexts (HTTPS or localhost).
// The deployed site is served over plain HTTP, so every copy action must fall
// back to the legacy selection-based path instead of throwing on undefined.
export async function copyText(text: string): Promise<boolean> {
  const clipboard = typeof navigator !== 'undefined' ? navigator.clipboard : undefined
  if (clipboard && typeof clipboard.writeText === 'function') {
    try {
      await clipboard.writeText(text)
      return true
    } catch {
      // Permission denied or document not focused; fall through to execCommand.
    }
  }
  return copyTextWithExecCommand(text)
}

function copyTextWithExecCommand(text: string): boolean {
  if (typeof document === 'undefined') return false
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '-9999px'
  document.body.appendChild(textarea)
  const selection = document.getSelection()
  const previousRange = selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null
  textarea.select()
  textarea.setSelectionRange(0, text.length)
  let copied = false
  try {
    copied = document.execCommand('copy')
  } catch {
    // execCommand throws in some embedded webviews; treat as a failed copy.
  }
  document.body.removeChild(textarea)
  if (previousRange && selection) {
    selection.removeAllRanges()
    selection.addRange(previousRange)
  }
  return copied
}
