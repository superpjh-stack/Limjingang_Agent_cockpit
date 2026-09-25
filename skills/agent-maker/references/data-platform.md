# Read-only manufacturing data platform

Use this reference when connecting equipment, sensor-history, tag-catalog, or CCP endpoints.

## Server boundary

- Read the base URL and API key from server environment variables. Send the key only in the upstream authentication header.
- Expose narrow function tools instead of a generic URL, SQL, or request tool.
- Validate equipment codes, date ranges, intervals, and limits before the upstream request.
- Use a bounded timeout appropriate to the source. Historical analytics may be slower than latest-value endpoints.
- Convert upstream failures to `데이터 플랫폼 연결 실패 (코드) — 메시지` and let the rest of the workspace continue.

## Recommended tool categories

- `list_tags`: equipment, item keys, units, and configured CCP references.
- `get_latest`: latest readings and freshness for one or all equipment.
- `get_readings`: bounded raw or hourly history for a specific equipment and item.
- `get_ccp_excursions`: dated summaries of samples outside configured criteria.

Keep these read-only. In answers, attach units and KST timestamps. Distinguish an excursion sample count from an alarm-event count. If an equipment code is unknown, call the tag catalog before querying readings.

## Recommendation quality

Before publishing process-data recommendations, map each question to at least one configured tool. Verify representative calls for the tag catalog, latest values, history, and CCP summary. General manufacturing explanations belong in a separate recommendation group.

