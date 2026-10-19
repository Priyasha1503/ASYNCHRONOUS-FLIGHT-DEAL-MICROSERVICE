# ADDITIONAL MANDATORY REQUIREMENTS: DESIGN INSPIRATION, VISUAL QUALITY, AND CREATIVE PRODUCT THINKING

These requirements extend the original SkyScout AI specification and are mandatory.

## A. Design Inspiration Is the Source of Truth

I will provide visual inspiration during development. This may include screenshots, reference websites, images, UI examples, color palettes, typography samples, animations, layouts, and specific design details I like.

Treat these references as important product requirements, not optional suggestions.

Before implementing or substantially redesigning the UI:

1. Inspect every supplied reference image and accessible reference asset.
2. Identify its visual style, color palette, typography, spacing, layout, component hierarchy, border treatment, shadows, imagery, motion, and interaction patterns.
3. Identify the exact elements worth adapting for SkyScout AI.
4. Distinguish between elements I want reproduced closely and elements that should be adapted to flight discovery.
5. Create a concise design analysis and an initial design specification.
6. Ask a focused clarification only if an essential design choice is genuinely ambiguous.

Do not invent my preferences when I have provided references.

If I provide multiple references, combine their strongest compatible elements into one cohesive design system rather than creating disconnected screens.

If the references conflict, prioritize explicit instructions and the references I identify as most important.

Preserve the inspiration's visual character while creating original, coherent SkyScout AI branding. Do not copy another company's logo, proprietary assets, or exact branded identity.

### How to handle the reference images

Support a reference directory such as:

`design-references/`

Use descriptive filenames where possible, for example:
- `landing-page-reference.png`
- `flight-results-layout.png`
- `preferred-colors.png`
- `dashboard-reference.png`
- `animation-reference.gif`

Inspect the actual assets available in the repository. If an image is inaccessible or its contents cannot be inspected, tell me rather than pretending to have analyzed it.

If I provide a reference website, inspect it when browsing tools and access permit. Do not assume a screenshot reveals how its interactions work.

Maintain `docs/DESIGN_BRIEF.md` and `docs/DESIGN_DECISIONS.md` with the references, design interpretations, chosen tokens, component rules, and any deliberate deviations.

Whenever I add new inspiration, revisit the design decisions and update the affected components without unnecessarily breaking existing functionality.

## B. Create a Distinct Visual Identity

Do not automatically generate a generic AI startup interface with a blue-purple gradient, oversized headings, and identical rounded cards.

Derive SkyScout AI's visual identity from my inspiration.

Define:
- Primary, secondary, and accent colors.
- Page, surface, and elevated-surface colors.
- Text, muted-text, border, and divider colors.
- Success, warning, error, and informational colors.
- Typography families, weights, and type scales.
- Spacing and layout tokens.
- Border radii, shadows, and elevation levels.
- Iconography rules.
- Image aspect ratios and cropping rules.
- Button, input, dropdown, modal, tooltip, and card styles.
- Chart colors and data-visualization conventions.
- Motion, transitions, and interaction states.

Store reusable tokens centrally using CSS variables and Tailwind configuration where appropriate.

Use a consistent design system across the landing page, search form, results, flight cards, price charts, saved trips, alerts, and account screens.

Do not choose colors merely because they are popular. Choose them because they serve the supplied visual direction, accessibility, readability, and product identity.

Ensure adequate contrast and readable data labels. Never communicate a fare status using color alone.

## C. Premium UI Quality Bar

The finished application must feel like a thoughtfully designed, polished travel-tech product.

Pay attention to the details that distinguish excellent interfaces from merely functional ones:

- Strong visual hierarchy.
- Precise alignment and consistent spacing.
- Excellent typography and line lengths.
- Balanced density of flight information.
- Refined buttons, inputs, menus, and dropdowns.
- Thoughtful hover, focus, active, disabled, loading, and error states.
- Beautiful empty states with useful next actions.
- Responsive layouts rather than desktop designs squeezed onto mobile.
- Consistent icon sizes and stroke styles.
- Appropriate image cropping and aspect ratios.
- Subtle, purposeful animations.
- Smooth navigation and transitions.
- Useful microcopy and clear status messages.
- No accidental layout shifts when data arrives.
- No horizontal overflow or broken components at common screen sizes.

Avoid visual clutter, excessive gradients, gratuitous glassmorphism, excessive shadows, and unnecessary animations unless they are supported by my inspiration.

Do not use placeholder rectangles as the final treatment for important content. Use suitable imagery, icons, real interface elements, and intentional empty states.

Use real flight data when available and realistic deterministic fixtures otherwise.

The UI must distinguish mock data from live data.

## D. Make the Flight Results Experience Exceptional

Treat the results page as the most important screen in the product.

Design a clear hierarchy containing:

1. Search summary and editable search criteria.
2. A compact overview of result count, provider coverage, and freshness.
3. Cheapest qualifying flight.
4. Best overall match.
5. Other ranked flight results.
6. Sorting and filtering controls.
7. Fare, baggage, stop, duration, and schedule comparisons where data is available.
8. Price history and monitoring actions.
9. Clear booking or provider-redirection actions.

Do not make every result card look equally important.

Users should understand quickly:
- Which flight is cheapest while meeting their requirements.
- Which flight offers the best trade-off.
- Why each recommendation was selected.
- Whether a price is fresh, cached, stale, or unverified.
- What is included in the fare.
- What remains unknown.

Use progressive disclosure for secondary details. Keep the primary decision-making information easy to scan.

On mobile, prioritize a compact search summary, readable fare cards, accessible filters, and a clear comparison flow.

## E. Create Delight Without Sacrificing Usability

Introduce purposeful product details such as:
- A satisfying but brief search-progress animation.
- Live provider status updates.
- Smooth transitions when new flight results arrive.
- Clear visual feedback when a user saves a trip or activates an alert.
- Price-drop indicators with the actual observation timestamp.
- Interactive price-history charts.
- A polished monitoring timeline.
- Helpful empty states for users who have not saved a trip.
- A well-designed first-time onboarding experience.
- Thoughtful loading placeholders that resemble the final content.
- Clear recovery actions after failed searches.

Use Framer Motion or another suitable animation solution only where it improves the experience.

Respect reduced-motion preferences, avoid blocking interactions, and keep animations performant on lower-end devices.

Do not add artificial loading delays to make the product appear sophisticated.

## F. Functional Completeness Matters as Much as Appearance

Every visible control must have a meaningful behavior.

Search buttons must initiate real application searches. Filters must change results. Sorting must reorder results. Save buttons must persist saved state. Alert controls must configure real monitoring rules.

If a feature depends on unavailable credentials, provide an explicitly labeled demo mode or a clear unavailable state.

Do not create decorative controls that imply unsupported functionality.

Use reusable components, typed interfaces, consistent loading states, and clear separation between presentation and business logic.

Keep the interface responsive to real API latency and partial provider failures.

## G. Mandatory Visual Quality Assurance

Do not declare the frontend finished simply because it compiles.

After implementing each major screen:

1. Start the application.
2. Use browser-based testing or Playwright to inspect the actual rendered interface where the environment permits.
3. Capture screenshots at desktop and mobile viewport sizes.
4. Compare the screenshots against the supplied inspiration and `docs/DESIGN_BRIEF.md`.
5. Identify differences in layout, spacing, typography, colors, density, image treatment, and hierarchy.
6. Correct the most important discrepancies.
7. Test loading, empty, success, partial-result, error, and responsive states.
8. Repeat the visual review after substantial UI changes.

Check for:
- Overflow and clipped content.
- Misaligned components.
- Inconsistent spacing.
- Unreadable or low-contrast text.
- Incorrect image ratios.
- Layout shifts.
- Broken mobile navigation.
- Inconsistent design tokens.
- Console errors and failed network requests.
- Inaccessible keyboard interactions.

Use screenshot comparison where practical, but do not rely exclusively on pixel-perfect matching. Verify functionality and usability as well.

Report which viewports and states were actually tested. Never claim visual testing was completed if the application could not be rendered or inspected.

## H. Continuous Design Collaboration

I may provide additional images and inspiration while development is in progress.

When I do:

1. Analyze the new reference.
2. Identify the affected screens and shared components.
3. Update the design specification.
4. Explain the proposed visual changes briefly.
5. Implement the changes using existing design tokens and reusable components.
6. Check that previously completed screens remain visually consistent.
7. Rerun relevant functional and visual tests.

Do not redesign the entire application unnecessarily when the new reference affects only one section.

My inspiration should influence the product from the first UI implementation through final visual QA, not only the landing page.

## I. Additional Product and Engineering Improvements

Think critically like a software engineer building a real travel product.

Prioritize these enhancements when the core search, caching, and monitoring workflow is stable:

1. Flexible-date and nearby-airport discovery, with mandatory constraints preserved.
2. True-value fare comparison that clearly separates known costs from unavailable information.
3. A target-price feature based on observed price history.
4. A monitoring center with freshness, last-check time, next-check status, and provider health.
5. A provider quota and request-cost dashboard.
6. Search-quality metrics and feedback about whether recommendations were useful.
7. Accessible interfaces and resilient behavior on slow networks.
8. Privacy-conscious analytics and error reporting.
9. A documented capacity model and repeatable load-test scenarios.
10. A clear distinction between historical observations, estimates, and verified current offers.

Avoid implementing every idea at once. Prioritize based on user value, engineering risk, dependencies, and available time.

For every major feature, explain the benefit, implementation cost, dependencies, and acceptance criteria.

## J. Updated Definition of Done

A feature is complete only when:
- Its intended behavior is implemented.
- Its loading, empty, error, and success states are considered.
- Its UI follows the established design system.
- Its functionality has been tested.
- Its responsive behavior has been reviewed.
- Its accessibility has been considered.
- Its documentation is updated where necessary.

A screen is not complete merely because it looks attractive in a static screenshot.

The final product must combine strong visual identity, accurate flight information, transparent recommendations, reliable background processing, and an excellent user experience.

These design requirements are mandatory additions to the original SkyScout AI master prompt.