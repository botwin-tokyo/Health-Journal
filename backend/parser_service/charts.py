"""Inline SVG from frozen scalar points only; never fetch resources or fill gaps."""

import html
from datetime import date
from decimal import Decimal, InvalidOperation


def frozen_charts(sections):
    series = {}
    for section in sections:
        try:
            day = date.fromisoformat(section["clinical_date"])
        except (KeyError, TypeError, ValueError):
            continue
        data = section.get("data", {})
        values = (
            {
                "Weight (" + data.get("display_unit", "kg") + ")": data.get(
                    "display_value", data.get("canonical_value")
                )
            }
            if data.get("metric_id") == "weight"
            else {
                name + " (" + str(data.get("units", {}).get(name, "")) + ")": value
                for name, value in data.get("values", {}).items()
            }
        )
        for name, value in values.items():
            if value is None:
                continue
            try:
                number = Decimal(str(value))
            except InvalidOperation:
                continue
            if number.is_finite():
                series.setdefault(name, []).append((day, number))
    output = []
    for name, points in series.items():
        if len(points) < 2:
            continue
        points.sort()
        days = [day.toordinal() for day, _ in points]
        values = [value for _, value in points]
        low, high = min(values), max(values)
        span = high - low or Decimal(1)
        width = max(days) - min(days) or 1
        markers = []
        segments = []
        previous = None
        for (day, value), ordinal in zip(points, days):
            x = Decimal(30) + Decimal(480 * (ordinal - min(days))) / Decimal(width)
            y = Decimal(140) - (value - low) / span * Decimal(100)
            coordinate = f"{x:.2f},{y:.2f}"
            if previous is None or ordinal - previous > 1:
                segments.append("M" + coordinate)
            else:
                segments.append("L" + coordinate)
            markers.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3"/>')
            previous = ordinal
        output.append(
            "<section><h2>"
            + html.escape(name)
            + '</h2><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 180" role="img"><title>'
            + html.escape(name)
            + ' — frozen source points; gaps preserved</title><path d="'
            + " ".join(segments)
            + '" fill="none" stroke="#b22" stroke-width="2"/><g fill="#b22">'
            + "".join(markers)
            + '</g><text x="30" y="170" font-size="10">'
            + points[0][0].isoformat()
            + '</text><text x="440" y="170" font-size="10">'
            + points[-1][0].isoformat()
            + '</text><text x="30" y="20" font-size="10">'
            + html.escape(str(low) + " to " + str(high))
            + "</text></svg></section>"
        )
    return "".join(output)
