import React from 'react';
import { Cpu, AlertCircle, CheckCircle } from 'lucide-react';
import { EngineCapabilityData } from '../types/api';

interface EngineSelectorProps {
  engines: EngineCapabilityData[];
  selectedEngineId: string;
  onSelectEngine: (id: string) => void;
  disabled?: boolean;
}

export const EngineSelector: React.FC<EngineSelectorProps> = ({
  engines,
  selectedEngineId,
  onSelectEngine,
  disabled = false,
}) => {
  const selectedEngine = engines.find((e) => e.engine_id === selectedEngineId);

  return (
    <div>
      <label htmlFor="engine-select" className="block text-sm font-semibold text-slate-800 mb-1.5 flex items-center space-x-1.5">
        <Cpu className="w-4 h-4 text-blue-700" />
        <span>OCR Recognition Engine</span>
      </label>

      <div className="relative">
        <select
          id="engine-select"
          value={selectedEngineId}
          onChange={(e) => onSelectEngine(e.target.value)}
          disabled={disabled || engines.length === 0}
          className="w-full bg-white border border-slate-300 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-shadow disabled:bg-slate-100 disabled:cursor-not-allowed shadow-sm"
        >
          {engines.map((eng) => (
            <option key={eng.engine_id} value={eng.engine_id}>
              {eng.display_name} {eng.is_available ? '✓' : '(Not Installed)'}
            </option>
          ))}
        </select>
      </div>

      {selectedEngine && (
        <div className="mt-1.5 flex items-center space-x-1.5 text-xs">
          {selectedEngine.is_available ? (
            <span className="text-emerald-700 flex items-center font-medium">
              <CheckCircle className="w-3.5 h-3.5 mr-1 text-emerald-600" />
              Engine ready • Supported scripts: {selectedEngine.supported_scripts.join(', ')}
            </span>
          ) : (
            <span className="text-amber-700 flex items-center font-medium">
              <AlertCircle className="w-3.5 h-3.5 mr-1 text-amber-600" />
              {selectedEngine.unavailability_reason || 'Engine runtime not found on host machine'}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
