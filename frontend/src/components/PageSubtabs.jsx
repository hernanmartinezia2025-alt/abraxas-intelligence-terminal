import React from "react";

export default function PageSubtabs({ tabs, activeTab, onChange }) {
  return (
    <nav className="page-subtabs" aria-label="Subsecciones de la página">
      {tabs.map(([key, label, detail]) => (
        <button
          className={activeTab === key ? "active" : ""}
          type="button"
          key={key}
          onClick={() => onChange(key)}
          aria-selected={activeTab === key}
          role="tab"
        >
          <span>{label}</span>
          <small>{detail}</small>
        </button>
      ))}
    </nav>
  );
}
