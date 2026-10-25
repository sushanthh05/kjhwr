import React from 'react'

export default function SectionCard({
  id,
  title,
  subtitle,
  icon: Icon,
  badge,
  actions,
  children,
  className = '',
}) {
  return (
    <section id={id} className={`section-card ${className}`}>
      {(title || Icon || actions) && (
        <div className="section-header">
          <div className="section-title-wrapper">
            {Icon && (
              <div className="section-icon">
                <Icon size={18} />
              </div>
            )}
            <div>
              <div className="section-title-row">
                <h2 className="section-title">{title}</h2>
                {badge && <span className="section-badge">{badge}</span>}
              </div>
              {subtitle && <p className="section-subtitle">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="section-actions">{actions}</div>}
        </div>
      )}
      <div className="section-body">{children}</div>
    </section>
  )
}
