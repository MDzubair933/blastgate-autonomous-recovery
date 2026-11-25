# BlastGate dashboard design system

This is the current dark dashboard system. The historical AWS Startups light-theme reference remains unchanged as design history; it is not the current palette authority.

| Role | Value |
|---|---|
| Canvas | `#0B0F14` |
| Sidebar/inset | `#0D1117` |
| Panel | `#11161D` |
| Elevated | `#161B22` |
| Primary text | `#F5F4F1` |
| Secondary text | `#B5B8BD` |
| Metadata | `#A1A8B2` / `#848B95` |
| Action/accent | `#D8A955`, hover/focus `#E6BB73` |
| Healthy/refused | Emerald/red with text labels; never color alone |
| Border | White at 10% opacity; quiet tabs use a gold underline for selection |

Use Cormorant Garamond/Georgia for editorial headings, Inter/system sans for controls and explanatory text, and monospace only for identifiers/data. Existing Google Fonts loading is optional; the fallback stack must remain usable offline. Screenshots must disclose which fonts actually rendered when network access is unavailable.

The presentation views use flat summary bands, ruled lists and 36–44px section spacing. Reserve panels for the principal decision outcome. Editorial headings scale from 38px on phones to 60px on desktop; normal copy uses sans, while tokens, IDs and code use mono. Technical detail uses native disclosures, closed by default. Desktop navigation is 240px; below 1024px it becomes a keyboard-managed drawer. Main content stacks on narrow screens. Long hashes and source references wrap or scroll inside their own inspector rather than widening the page.

Every view retains the visible mode label. Recorded data has source category, captured timestamp and scope. Do not add animated live dots to historical status, invent incident durations, or replace a missing value with zero. Motion is restrained and disabled for reduced-motion preferences. Visible focus rings, labels and native disclosure controls take priority over decorative effects.

See the [UI refinement changelog](UI_REFINEMENT_CHANGELOG.md) for screenshot choices, visible-copy measurements and validation.
