import React from 'react';
import { LayoutGrid } from 'lucide-react';
import { FormTemplateSummary } from '../types/api';

interface TemplateSelectorProps {
  templates: FormTemplateSummary[];
  selectedTemplateId: string;
  onSelectTemplate: (id: string) => void;
  disabled?: boolean;
}

export const TemplateSelector: React.FC<TemplateSelectorProps> = ({
  templates,
  selectedTemplateId,
  onSelectTemplate,
  disabled = false,
}) => {
  const selectedTemplate = templates.find((t) => t.template_id === selectedTemplateId);

  return (
    <div>
      <label htmlFor="template-select" className="block text-sm font-semibold text-slate-800 mb-1.5 flex items-center space-x-1.5">
        <LayoutGrid className="w-4 h-4 text-blue-700" />
        <span>Form Layout Template</span>
      </label>

      <div className="relative">
        <select
          id="template-select"
          value={selectedTemplateId}
          onChange={(e) => onSelectTemplate(e.target.value)}
          disabled={disabled || templates.length === 0}
          className="w-full bg-white border border-slate-300 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-shadow disabled:bg-slate-100 disabled:cursor-not-allowed shadow-sm"
        >
          {templates.map((tpl) => (
            <option key={tpl.template_id} value={tpl.template_id}>
              {tpl.name} ({tpl.field_count} fields • {tpl.canonical_width}x{tpl.canonical_height}px)
            </option>
          ))}
        </select>
      </div>

      {selectedTemplate && (
        <p className="mt-1.5 text-xs text-slate-500">
          {selectedTemplate.description}
        </p>
      )}
    </div>
  );
};
