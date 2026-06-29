import { useState } from 'react';
import {
  Database, ArrowLeft, FileBarChart, Settings, Search,
  Download, FileSpreadsheet, Calendar, FlaskConical,
  AlertTriangle, Thermometer, Droplets, Wind, Clock,
  BarChart3, Activity
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend, CartesianGrid
} from 'recharts';

/* ── Mock Data ───────────────────────────────────────────── */

const TANKS = ['F-001','F-002','F-003','F-004','F-005','F-006','F-007','F-008','F-009','F-010','F-011','F-012'];
const STATUS_LIST = ['进行中','已完成','已终止'] as const;
const EXCEPTION_TYPES = ['温度异常','pH异常','溶氧异常'] as const;
const SEVERITY_LIST = ['严重','中等','轻微'] as const;

type Batch = { id: string; tank: string; start: string; end: string; status: string; exceptions: number };

const BATCH_DATA: Batch[] = Array.from({ length: 27 }, (_, i) => {
  const idx = i + 1;
  const month = String(Math.ceil(idx / 5)).padStart(2, '0');
  const day = String(((idx % 28) || 1)).padStart(2, '0');
  const status = idx <= 8 ? '进行中' : idx <= 22 ? '已完成' : '已终止';
  const exc = idx % 4 === 0 ? (idx % 3) + 1 : 0;
  return {
    id: `B2026${String(idx).padStart(3, '0')}`,
    tank: TANKS[idx % TANKS.length],
    start: `2026-${month}-${day} 08:00`,
    end: `2026-${month}-${day} 20:00`,
    status,
    exceptions: exc,
  };
});

const BAR_DATA = [
  { name: 'B2026001', yield: 120, errors: 2 }, { name: 'B2026002', yield: 98, errors: 0 },
  { name: 'B2026003', yield: 135, errors: 1 }, { name: 'B2026004', yield: 110, errors: 4 },
  { name: 'B2026005', yield: 145, errors: 0 }, { name: 'B2026006', yield: 88, errors: 3 },
  { name: 'B2026007', yield: 155, errors: 1 }, { name: 'B2026008', yield: 102, errors: 0 },
];

const PIE_DATA = [
  { name: '温度异常', value: 15, color: '#ef4444' },
  { name: 'pH异常', value: 12, color: '#f59e0b' },
  { name: '溶氧异常', value: 18, color: '#8b5cf6' },
];

const ANOMALY_ROWS = Array.from({ length: 15 }, (_, i) => {
  const idx = i + 1;
  const type = EXCEPTION_TYPES[idx % 3];
  const sev = idx <= 4 ? '严重' : idx <= 9 ? '中等' : '轻微';
  return {
    id: `E${String(idx).padStart(4, '0')}`,
    batch: `B2026${String(idx).padStart(3, '0')}`,
    tank: TANKS[idx % TANKS.length],
    type,
    start: `2026-06-${String(10 + idx).padStart(2, '0')} ${8 + (idx % 12)}:00`,
    end: `2026-06-${String(10 + idx).padStart(2, '0')} ${8 + (idx % 12) + 1}:30`,
    duration: `${1 + (idx % 3)}h ${(idx * 17) % 60}min`,
    severity: sev,
  };
});

const ANOMALY_COMPARE = [
  { name: 'F-001', temp: 3, ph: 2, do2: 1 }, { name: 'F-002', temp: 2, ph: 4, do2: 2 },
  { name: 'F-003', temp: 1, ph: 1, do2: 3 }, { name: 'F-004', temp: 4, ph: 0, do2: 2 },
  { name: 'F-005', temp: 2, ph: 3, do2: 1 }, { name: 'F-006', temp: 0, ph: 2, do2: 4 },
  { name: 'F-007', temp: 3, ph: 0, do2: 3 }, { name: 'F-008', temp: 0, ph: 0, do2: 2 },
];

const RAW_DATA_ROWS = Array.from({ length: 20 }, (_, i) => {
  const idx = i + 1;
  const isAnomaly = idx % 5 === 0;
  return {
    id: idx,
    batch: `B2026${String(((idx % 27) + 1)).padStart(3, '0')}`,
    tank: TANKS[idx % TANKS.length],
    time: `2026-06-${String(20 + (idx % 9)).padStart(2, '0')} ${String((idx * 3) % 24).padStart(2, '0')}:${String((idx * 7) % 60).padStart(2, '0')}`,
    temp: +(36.5 + (idx % 5) * 0.3).toFixed(1),
    ph: +(7.0 - (idx % 4) * 0.1).toFixed(1),
    dissolvedO2: +(45 + (idx * 3) % 20).toFixed(1),
    agitation: 150 + (idx * 10) % 100,
    pressure: +(0.05 + (idx % 3) * 0.01).toFixed(2),
    level: +(60 + (idx * 5) % 30).toFixed(1),
    anomaly: isAnomaly,
  };
});

const TANK_VOLUME_DATA = [
  { name: 'F-001', count: 4200 }, { name: 'F-002', count: 3800 },
  { name: 'F-003', count: 4500 }, { name: 'F-004', count: 3200 },
  { name: 'F-005', count: 4100 }, { name: 'F-006', count: 3900 },
  { name: 'F-007', count: 4800 }, { name: 'F-008', count: 3600 },
  { name: 'F-009', count: 4300 }, { name: 'F-010', count: 3100 },
  { name: 'F-011', count: 4700 }, { name: 'F-012', count: 3500 },
];

const TIME_DIST_DATA = [
  { name: '06-20', value: 1200 }, { name: '06-21', value: 1800 },
  { name: '06-22', value: 2400 }, { name: '06-23', value: 2100 },
  { name: '06-24', value: 2800 }, { name: '06-25', value: 3200 },
  { name: '06-26', value: 2900 }, { name: '06-27', value: 3500 },
  { name: '06-28', value: 3100 }, { name: '06-29', value: 2600 },
];

/* ── Helpers ──────────────────────────────────────────────── */

const statusColor = (s: string) =>
  s === '进行中' ? 'bg-blue-500/15 text-blue-600' :
  s === '已完成' ? 'bg-green-500/15 text-green-600' :
  'bg-red-500/15 text-red-600';

const severityColor = (s: string) =>
  s === '严重' ? 'bg-red-500/15 text-red-600' :
  s === '中等' ? 'bg-orange-500/15 text-orange-500' :
  'bg-blue-500/15 text-blue-500';

const excTypeColor = (t: string) =>
  t === '温度异常' ? 'bg-red-500/15 text-red-600' :
  t === 'pH异常' ? 'bg-orange-500/15 text-orange-500' :
  'bg-purple-500/15 text-purple-500';

/* ── Reusable Bits ────────────────────────────────────────── */

function Badge({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${className}`}>{children}</span>;
}

function StatCard({ label, value, icon: Icon, accent, accentText }: {
  label: string; value: string | number; icon: React.ElementType; accent: string; accentText: string;
}) {
  return (
    <div className={`bg-card border border-border rounded-xl p-5 border-t-4 ${accent}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-muted-foreground">{label}</span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${accentText}`}>
          <Icon size={16} />
        </div>
      </div>
      <div className="text-3xl font-bold text-foreground">{value}</div>
    </div>
  );
}

function Pagination({ page, total, perPage, onChange }: {
  page: number; total: number; perPage: number; onChange: (p: number) => void;
}) {
  const pages = Math.ceil(total / perPage);
  return (
    <div className="flex items-center gap-2 mt-4">
      <button onClick={() => onChange(Math.max(1, page - 1))} disabled={page === 1}
        className="px-3 py-1 text-sm rounded-md border border-border hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed">
        上一页
      </button>
      {Array.from({ length: pages }, (_, i) => i + 1).map(p => (
        <button key={p} onClick={() => onChange(p)}
          className={`w-8 h-8 text-sm rounded-md border ${p === page ? 'bg-blue-600 text-white border-blue-600' : 'border-border hover:bg-secondary'}`}>
          {p}
        </button>
      ))}
      <button onClick={() => onChange(Math.min(pages, page + 1))} disabled={page === pages}
        className="px-3 py-1 text-sm rounded-md border border-border hover:bg-secondary disabled:opacity-40 disabled:cursor-not-allowed">
        下一页
      </button>
    </div>
  );
}

/* ── Main Component ───────────────────────────────────────── */

export default function FermentExportPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'anomaly' | 'raw'>('overview');
  const [selectedBatches, setSelectedBatches] = useState<Set<string>>(new Set());
  const [tankFilter, setTankFilter] = useState('');
  const [batchSearch, setBatchSearch] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  const toggleBatch = (id: string) => {
    setSelectedBatches(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = (ids: string[]) => {
    setSelectedBatches(prev => {
      const all = ids.every(id => prev.has(id));
      const next = new Set(prev);
      all ? ids.forEach(id => next.delete(id)) : ids.forEach(id => next.add(id));
      return next;
    });
  };

  const filteredBatches = BATCH_DATA.filter(b => {
    if (tankFilter && b.tank !== tankFilter) return false;
    if (batchSearch && !b.id.toLowerCase().includes(batchSearch.toLowerCase())) return false;
    return true;
  });

  const perPage = 10;
  const paginatedBatches = filteredBatches.slice((currentPage - 1) * perPage, currentPage * perPage);

  const tabs = [
    { key: 'overview' as const, label: '数据总览' },
    { key: 'anomaly' as const, label: '异常记录' },
    { key: 'raw' as const, label: '原始数据' },
  ];

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* ── Sidebar ────────────────────────────────────── */}
      <aside className="w-52 bg-slate-900 text-white flex flex-col shrink-0">
        <div className="px-4 py-5 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <FlaskConical size={20} className="text-blue-400" />
            <span className="font-semibold text-sm">酶蛋白AI平台</span>
          </div>
        </div>
        <nav className="flex-1 py-4 px-2 space-y-1">
          <a href="#" className="flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg text-slate-400 hover:text-white hover:bg-slate-800">
            <ArrowLeft size={16} /> 返回管理后台
          </a>
          <a href="#" className="flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg bg-blue-600 text-white">
            <Database size={16} /> 发酵数据导出
          </a>
          <a href="#" className="flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg text-slate-400 hover:text-white hover:bg-slate-800">
            <FileBarChart size={16} /> 历史分析报告
          </a>
          <a href="#" className="flex items-center gap-3 px-3 py-2.5 text-sm rounded-lg text-slate-400 hover:text-white hover:bg-slate-800">
            <Settings size={16} /> 系统设置
          </a>
        </nav>
      </aside>

      {/* ── Main ───────────────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <Database size={20} className="text-blue-600" />
            <h1 className="text-lg font-semibold">发酵数据导出</h1>
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 bg-blue-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-blue-700 transition-colors">
              <Download size={14} /> 导出
            </button>
            <button className="flex items-center gap-2 bg-green-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-green-700 transition-colors">
              <FileSpreadsheet size={14} /> 导出 Excel
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* ── Filter Bar ─────────────────────────────── */}
          <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-muted-foreground" />
              <span className="text-sm text-muted-foreground whitespace-nowrap">时间范围</span>
              <input type="date" className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm" />
              <span className="text-muted-foreground text-sm">~</span>
              <input type="date" className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm" />
            </div>
            <div className="flex items-center gap-2">
              <FlaskConical size={14} className="text-muted-foreground" />
              <span className="text-sm text-muted-foreground whitespace-nowrap">发酵罐</span>
              <select value={tankFilter} onChange={e => { setTankFilter(e.target.value); setCurrentPage(1); }}
                className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm min-w-[100px]">
                <option value="">全部</option>
                {TANKS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Search size={14} className="text-muted-foreground" />
              <span className="text-sm text-muted-foreground whitespace-nowrap">批次号</span>
              <input type="text" value={batchSearch} onChange={e => { setBatchSearch(e.target.value); setCurrentPage(1); }}
                placeholder="输入批次号搜索" className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm min-w-[140px]" />
            </div>
            <button className="flex items-center gap-2 bg-blue-600 text-white rounded-lg px-4 py-1.5 text-sm hover:bg-blue-700 transition-colors">
              <Search size={14} /> 查询
            </button>
          </div>

          {/* ── Batch Selection Table ──────────────────── */}
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div className="flex items-center gap-2">
                <h2 className="font-semibold">批次选择</h2>
              </div>
              <span className="text-sm text-muted-foreground">已选 <span className="text-blue-600 font-medium">{selectedBatches.size}</span> / {filteredBatches.length} 条</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-secondary text-xs uppercase text-muted-foreground">
                    <th className="px-4 py-3 text-left font-medium">
                      <input type="checkbox"
                        checked={paginatedBatches.every(b => selectedBatches.has(b.id))}
                        onChange={() => toggleAll(paginatedBatches.map(b => b.id))}
                        className="rounded border-border" />
                    </th>
                    <th className="px-4 py-3 text-left font-medium">批次号</th>
                    <th className="px-4 py-3 text-left font-medium">发酵罐</th>
                    <th className="px-4 py-3 text-left font-medium">开始时间</th>
                    <th className="px-4 py-3 text-left font-medium">结束时间</th>
                    <th className="px-4 py-3 text-left font-medium">状态</th>
                    <th className="px-4 py-3 text-left font-medium">异常标记</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {paginatedBatches.map(b => (
                    <tr key={b.id} className="hover:bg-secondary/50 transition-colors">
                      <td className="px-4 py-3">
                        <input type="checkbox" checked={selectedBatches.has(b.id)} onChange={() => toggleBatch(b.id)} className="rounded border-border" />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{b.id}</td>
                      <td className="px-4 py-3">{b.tank}</td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">{b.start}</td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">{b.end}</td>
                      <td className="px-4 py-3"><Badge className={statusColor(b.status)}>{b.status}</Badge></td>
                      <td className="px-4 py-3">
                        {b.exceptions > 0
                          ? <Badge className="bg-red-500/15 text-red-600">{b.exceptions}次异常</Badge>
                          : <Badge className="bg-green-500/15 text-green-600">正常</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-5 py-4 border-t border-border flex items-center justify-between">
              <span className="text-xs text-muted-foreground">共 {filteredBatches.length} 条</span>
              <Pagination page={currentPage} total={filteredBatches.length} perPage={perPage} onChange={setCurrentPage} />
            </div>
          </div>

          {/* ── Tabs ───────────────────────────────────── */}
          <div>
            <div className="flex gap-6 border-b border-border">
              {tabs.map(t => (
                <button key={t.key} onClick={() => setActiveTab(t.key)}
                  className={`pb-3 text-sm font-medium transition-colors ${activeTab === t.key ? 'text-blue-600 border-b-2 border-blue-600' : 'text-muted-foreground hover:text-foreground'}`}>
                  {t.label}
                </button>
              ))}
            </div>

            {/* Tab 1: 数据总览 */}
            {activeTab === 'overview' && (
              <div className="mt-5 space-y-6">
                <div className="grid grid-cols-4 gap-4">
                  <StatCard label="总批次" value={156} icon={Database} accent="border-t-blue-500" accentText="bg-blue-500/15 text-blue-600" />
                  <StatCard label="异常批次" value={23} icon={AlertTriangle} accent="border-t-red-500" accentText="bg-red-500/15 text-red-600" />
                  <StatCard label="活跃发酵罐" value={12} icon={Activity} accent="border-t-green-500" accentText="bg-green-500/15 text-green-600" />
                  <StatCard label="平均时长" value="48.5h" icon={Clock} accent="border-t-purple-500" accentText="bg-purple-500/15 text-purple-600" />
                </div>

                <div className="grid grid-cols-7 gap-4">
                  <div className="col-span-4 bg-card border border-border rounded-xl p-5">
                    <h3 className="font-semibold mb-4 flex items-center gap-2"><BarChart3 size={16} className="text-blue-600" />按批次统计</h3>
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={BAR_DATA}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                        <YAxis tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                        <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                        <Legend />
                        <Bar dataKey="yield" name="产量" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="errors" name="异常次数" fill="#ef4444" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="col-span-3 bg-card border border-border rounded-xl p-5">
                    <h3 className="font-semibold mb-4 flex items-center gap-2"><AlertTriangle size={16} className="text-orange-500" />异常类型分布</h3>
                    <ResponsiveContainer width="100%" height={280}>
                      <PieChart>
                        <Pie data={PIE_DATA} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={{ fontSize: 11 }}>
                          {PIE_DATA.map(d => <Cell key={d.name} fill={d.color} />)}
                        </Pie>
                        <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: 异常记录 */}
            {activeTab === 'anomaly' && (
              <div className="mt-5 space-y-6">
                <div className="grid grid-cols-4 gap-4">
                  <StatCard label="总异常" value={45} icon={AlertTriangle} accent="border-t-red-500" accentText="bg-red-500/15 text-red-600" />
                  <StatCard label="温度异常" value={15} icon={Thermometer} accent="border-t-orange-500" accentText="bg-orange-500/15 text-orange-500" />
                  <StatCard label="pH异常" value={12} icon={Droplets} accent="border-t-blue-500" accentText="bg-blue-500/15 text-blue-500" />
                  <StatCard label="溶氧异常" value={18} icon={Wind} accent="border-t-purple-500" accentText="bg-purple-500/15 text-purple-500" />
                </div>

                <div className="bg-card border border-border rounded-xl p-5">
                  <h3 className="font-semibold mb-4 flex items-center gap-2"><BarChart3 size={16} className="text-blue-600" />异常类型对比</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={ANOMALY_COMPARE}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                      <YAxis tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                      <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                      <Legend />
                      <Bar dataKey="temp" name="温度异常" fill="#ef4444" radius={[3, 3, 0, 0]} />
                      <Bar dataKey="ph" name="pH异常" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                      <Bar dataKey="do2" name="溶氧异常" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-card border border-border rounded-xl overflow-hidden">
                  <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                    <h3 className="font-semibold">异常记录列表</h3>
                    <span className="text-xs text-muted-foreground">共 {ANOMALY_ROWS.length} 条</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-secondary text-xs uppercase text-muted-foreground">
                          <th className="px-4 py-3 text-left font-medium">异常ID</th>
                          <th className="px-4 py-3 text-left font-medium">批次号</th>
                          <th className="px-4 py-3 text-left font-medium">发酵罐</th>
                          <th className="px-4 py-3 text-left font-medium">异常类型</th>
                          <th className="px-4 py-3 text-left font-medium">开始时间</th>
                          <th className="px-4 py-3 text-left font-medium">结束时间</th>
                          <th className="px-4 py-3 text-left font-medium">持续时间</th>
                          <th className="px-4 py-3 text-left font-medium">严重程度</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {ANOMALY_ROWS.map(r => (
                          <tr key={r.id} className="hover:bg-secondary/50 transition-colors">
                            <td className="px-4 py-3 font-mono text-xs">{r.id}</td>
                            <td className="px-4 py-3 font-mono text-xs">{r.batch}</td>
                            <td className="px-4 py-3">{r.tank}</td>
                            <td className="px-4 py-3"><Badge className={excTypeColor(r.type)}>{r.type}</Badge></td>
                            <td className="px-4 py-3 text-muted-foreground text-xs">{r.start}</td>
                            <td className="px-4 py-3 text-muted-foreground text-xs">{r.end}</td>
                            <td className="px-4 py-3 text-xs">{r.duration}</td>
                            <td className="px-4 py-3"><Badge className={severityColor(r.severity)}>{r.severity}</Badge></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="px-5 py-4 border-t border-border">
                    <Pagination page={1} total={ANOMALY_ROWS.length} perPage={10} onChange={() => {}} />
                  </div>
                </div>
              </div>
            )}

            {/* Tab 3: 原始数据 */}
            {activeTab === 'raw' && (
              <div className="mt-5 space-y-6">
                <div className="grid grid-cols-3 gap-4">
                  <StatCard label="总数据量" value="45,680" icon={Database} accent="border-t-blue-500" accentText="bg-blue-500/15 text-blue-600" />
                  <StatCard label="发酵罐数" value={12} icon={Activity} accent="border-t-green-500" accentText="bg-green-500/15 text-green-600" />
                  <StatCard label="异常数据" value={45} icon={AlertTriangle} accent="border-t-red-500" accentText="bg-red-500/15 text-red-600" />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-card border border-border rounded-xl p-5">
                    <h3 className="font-semibold mb-4 flex items-center gap-2"><BarChart3 size={16} className="text-blue-600" />按发酵罐数据量</h3>
                    <ResponsiveContainer width="100%" height={260}>
                      <BarChart data={TANK_VOLUME_DATA}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                        <YAxis tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                        <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                        <Bar dataKey="count" name="数据量" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="bg-card border border-border rounded-xl p-5">
                    <h3 className="font-semibold mb-4 flex items-center gap-2"><Activity size={16} className="text-green-600" />数据时间分布</h3>
                    <ResponsiveContainer width="100%" height={260}>
                      <LineChart data={TIME_DIST_DATA}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                        <YAxis tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                        <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                        <Line type="monotone" dataKey="value" name="数据量" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="bg-card border border-border rounded-xl overflow-hidden">
                  <div className="px-5 py-4 border-b border-border flex items-center justify-between">
                    <h3 className="font-semibold">原始数据列表</h3>
                    <span className="text-xs text-muted-foreground">共 {RAW_DATA_ROWS.length} 条</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-secondary text-xs uppercase text-muted-foreground">
                          <th className="px-3 py-3 text-left font-medium">ID</th>
                          <th className="px-3 py-3 text-left font-medium">批次号</th>
                          <th className="px-3 py-3 text-left font-medium">发酵罐</th>
                          <th className="px-3 py-3 text-left font-medium">时间</th>
                          <th className="px-3 py-3 text-left font-medium">温度(°C)</th>
                          <th className="px-3 py-3 text-left font-medium">pH</th>
                          <th className="px-3 py-3 text-left font-medium">溶氧(%)</th>
                          <th className="px-3 py-3 text-left font-medium">搅拌转速(rpm)</th>
                          <th className="px-3 py-3 text-left font-medium">罐压(MPa)</th>
                          <th className="px-3 py-3 text-left font-medium">液位(%)</th>
                          <th className="px-3 py-3 text-left font-medium">异常标记</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {RAW_DATA_ROWS.map(r => (
                          <tr key={r.id} className="hover:bg-secondary/50 transition-colors">
                            <td className="px-3 py-3 text-xs">{r.id}</td>
                            <td className="px-3 py-3 font-mono text-xs">{r.batch}</td>
                            <td className="px-3 py-3 text-xs">{r.tank}</td>
                            <td className="px-3 py-3 text-muted-foreground text-xs">{r.time}</td>
                            <td className="px-3 py-3 text-xs">{r.temp}</td>
                            <td className="px-3 py-3 text-xs">{r.ph}</td>
                            <td className="px-3 py-3 text-xs">{r.dissolvedO2}</td>
                            <td className="px-3 py-3 text-xs">{r.agitation}</td>
                            <td className="px-3 py-3 text-xs">{r.pressure}</td>
                            <td className="px-3 py-3 text-xs">{r.level}</td>
                            <td className="px-3 py-3">
                              <span className={`inline-block w-2.5 h-2.5 rounded-full ${r.anomaly ? 'bg-red-500' : 'bg-green-500'}`} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="px-5 py-4 border-t border-border">
                    <Pagination page={1} total={RAW_DATA_ROWS.length} perPage={10} onChange={() => {}} />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
