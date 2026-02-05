# Components Consistency Guide

Goal: keep behaviors consistent across views by updating shared components, not per‑screen implementations.

Rules of thumb
- **Prefer shared components**: if a behavior exists in multiple places (tooltips, hover values, average lines), it belongs in a shared component.
- **Update at the source**: change the component once so all usages inherit it.
- **Avoid copy‑paste variants**: if a new use case appears, add options to the component rather than duplicating it.

Current shared components
- `ChartCard.jsx`: standard chart container layout.
- `InsightCard.jsx`: insight metric tile (label/value/tooltip).
- `MiniChart` (inside `ActivityDetail.jsx`): activity series charts.
- `InsightTrendChart` (inside `InsightTrend.jsx`): insights trend charts.

When you add a new chart behavior
1) Decide whether it belongs to **MiniChart** or **InsightTrendChart**.
2) Add the feature (hover tooltip, average line, axis labels) there.
3) Update styles in `styles.css` once.
4) Verify in **both**:
   - Activity charts (`/activity/:id`)
   - Insight trends (`/insights/:metric`)

If a behavior is missing somewhere
- First check if it’s a **different component**, then either:
  - port the behavior into that component, or
  - refactor to reuse the same component.

Checklist before shipping
- Hover tooltip shows value + unit.
- Average line is visible (dashed).
- Axes text size consistent.
- Chart container doesn’t overflow on mobile or desktop.
