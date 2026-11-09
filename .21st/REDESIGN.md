# Bloom website redesign

## Product homepage, 2026-11-08

The user requested an attractive advertising-style homepage. Retrieved [Hero with Product Mockup by vaib215](https://21st.dev/@vaib215/components/hero-with-product-mockup), catalog 4710, and adapted the headline, CTA and contextual product-preview composition to native HTML/CSS. Retained muted sage and existing local imagery. The labeled example uses actual rice/chicken reference math. No fake ratings, testimonials, health outcomes or phone-app availability claims.

The landing page scrolls; account access remains fixed-height. Initial landing access does not create or modify a journal. Explicit guest/create/sign-in actions use the existing flows, and errors are shown on the current surface. Journal/account, nutrition and server checks pass. Visual browser verification of this iteration was unavailable because the browser connection was disconnected.

Palette update, 2026-11-08: the user found the homepage too colorful. Bright lime and mixed blue/peach/lavender accents now use muted sage and neutral tones across the existing visual tokens. Login and overview retain their layout, controls and background-free imagery.

Implemented across login, signup, overview, food journal, photo review, activity, progress, goals, backup and native dialogs. Existing data formats, encryption and account flows are retained.

## Retrieved 21st.dev patterns

- [Health Stat Card, ruixen.ui](https://21st.dev/@ruixen.ui/components/health-stat-card), catalog 8617: primary metric, unit hierarchy and rounded chart bars.
- [Dashboard Sidebar, arunjdass](https://21st.dev/@arunjdass/components/dashboard-sidebar), catalog 14941: grouped icon navigation, active pill and profile footer.
- [Sign In 3, diarmuradi](https://21st.dev/@diarmuradi/components/sign-in-3), catalog 39096: split composition, compact labels and secondary entry path.

Code was retrieved with 21st search/get and adapted to the native stack; React components and animation dependencies were not installed. Hosted AI generation is disabled for this 21st account. Retrieved reference metadata is under `.21st/references/` in the source workspace.

## Verification

Browser checks cover all seven routes at desktop and 390px mobile widths without horizontal overflow. Login and signup fit without scrolling at 1366x768, 1024x600, 390x844, 375x667, 320x568 and 844x390. The landscape signup guest control was corrected after inspection.

An isolated guest journal was used to verify manual meal saving, totals and persistence after reload. Orange at 150g produced 70.5 kcal and 79.8mg vitamin C; logging it populated the consumed-food activity feed. Test meals were removed afterward. Real online AI inference requires an API key and was not exercised during this visual redesign.

The vault, nutrition and Python server regression checks remain part of the project. Screenshots are saved in the workspace as preview-21st-*.jpg.
