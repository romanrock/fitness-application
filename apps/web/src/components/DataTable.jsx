export default function DataTable({ columns, rows, footer }) {
  return (
    <div className="data-table">
      <div className="data-table__head">
        {columns.map((col) => (
          <div key={col.key} className="data-table__cell">{col.label}</div>
        ))}
      </div>
      {rows.map((row, idx) => (
        <div key={idx} className="data-table__row">
          {columns.map((col) => (
            <div key={col.key} className="data-table__cell">{row[col.key]}</div>
          ))}
        </div>
      ))}
      {footer && (
        <div className="data-table__row data-table__footer">
          {columns.map((col) => (
            <div key={col.key} className="data-table__cell">{footer[col.key] || ''}</div>
          ))}
        </div>
      )}
    </div>
  );
}
