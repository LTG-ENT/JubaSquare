import { useState, useEffect } from "react";
import { Cpu, HardDrive, Activity, Clock, TrendingUp, Database } from "lucide-react";

/**
 * Website Performance Monitor for Admin
 * Shows CPU, RAM, loading times, and other performance metrics
 */
export default function PerformanceMonitor() {
  const [stats, setStats] = useState({
    cpuUsage: 0,
    memoryUsage: 0,
    diskUsage: 0,
    responseTime: 0,
    activeConnections: 0,
    dbConnections: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadStats = async () => {
    try {
      // Measure API response time
      const start = performance.now();
      const response = await fetch('/api/health', { method: 'GET' });
      const end = performance.now();
      const responseTime = Math.round(end - start);

      if (response.ok) {
        const data = await response.json();
        setStats({
          cpuUsage: data.cpu_usage || 0,
          memoryUsage: data.memory_usage || 0,
          diskUsage: data.disk_usage || 0,
          responseTime,
          activeConnections: data.active_connections || 0,
          dbConnections: data.db_connections || 0,
        });
      } else {
        // Fallback to client-side metrics only
        setStats(prev => ({
          ...prev,
          responseTime,
        }));
      }
      setLoading(false);
    } catch (err) {
      console.error("Failed to load performance stats", err);
      setLoading(false);
    }
  };

  const getStatusColor = (value, type) => {
    if (type === 'response') {
      if (value < 200) return "text-green-600 bg-green-50";
      if (value < 500) return "text-yellow-600 bg-yellow-50";
      return "text-red-600 bg-red-50";
    }
    // For CPU, Memory, Disk
    if (value < 50) return "text-green-600 bg-green-50";
    if (value < 80) return "text-yellow-600 bg-yellow-50";
    return "text-red-600 bg-red-50";
  };

  const StatCard = ({ icon: Icon, label, value, suffix = "", type }) => (
    <div className="bg-white border border-[var(--js-border)] rounded-2xl p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${getStatusColor(value, type)}`}>
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">
              {label}
            </p>
            <p className="text-2xl font-bold text-[var(--js-text)] mt-0.5">
              {loading ? "..." : `${value}${suffix}`}
            </p>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="bg-white border border-[var(--js-border)] rounded-2xl p-5 sm:p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-[10px] uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">Monitoring</p>
          <h2 className="font-display font-bold text-lg text-[var(--js-text)] mt-0.5">Website Performance</h2>
          <p className="text-xs text-[var(--js-text-secondary)] mt-1">
            Real-time system metrics (updates every 5 seconds)
          </p>
        </div>
        <button
          onClick={loadStats}
          disabled={loading}
          className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white text-sm font-semibold rounded-xl transition disabled:opacity-50"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          icon={Cpu}
          label="CPU Usage"
          value={stats.cpuUsage}
          suffix="%"
          type="percentage"
        />
        <StatCard
          icon={HardDrive}
          label="Memory Usage"
          value={stats.memoryUsage}
          suffix="%"
          type="percentage"
        />
        <StatCard
          icon={Database}
          label="Disk Usage"
          value={stats.diskUsage}
          suffix="%"
          type="percentage"
        />
        <StatCard
          icon={Clock}
          label="API Response"
          value={stats.responseTime}
          suffix="ms"
          type="response"
        />
        <StatCard
          icon={Activity}
          label="Active Connections"
          value={stats.activeConnections}
          suffix=""
          type="count"
        />
        <StatCard
          icon={TrendingUp}
          label="DB Connections"
          value={stats.dbConnections}
          suffix=""
          type="count"
        />
      </div>

      <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-xl">
        <p className="text-xs text-blue-800">
          <strong>Note:</strong> Performance metrics require backend health endpoint. 
          If metrics show 0%, the endpoint may not be implemented yet. 
          API response time is always measured.
        </p>
      </div>
    </div>
  );
}
