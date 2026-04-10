import streamlit as st
import base64
import time
import threading
from io import BytesIO
from PIL import Image
import re

GPT_NANO_ENDPOINT = st.secrets["GPT_NANO_ENDPOINT"]
GPT_NANO_API_KEY = st.secrets["GPT_NANO_API_KEY"]
GPT_NANO_API_VERSION = st.secrets["GPT_NANO_API_VERSION"]
GPT_NANO_MODEL = st.secrets["GPT_NANO_MODEL"]

GPT_IMAGE_ENDPOINT = st.secrets["GPT_IMAGE_ENDPOINT"]
GPT_IMAGE_API_KEY = st.secrets["GPT_IMAGE_API_KEY"]
GPT_IMAGE_API_VERSION = st.secrets["GPT_IMAGE_API_VERSION"]
GPT_IMAGE_MODEL = st.secrets["GPT_IMAGE_MODEL"]


SYSTEM_PROMPT = """
You are an expert prompt engineer specializing in generating detailed image-generation
prompts for AI models (like gpt-image-1.5 or DALL-E). You analyze photos of handmade
clay, polymer clay, or play-dough figures and produce a structured multi-step
instructional poster prompt that would allow the image model to generate a complete
"How To Make" poster for that figure.
 
The number of steps is NOT fixed — you determine the right step count based on the
figure's actual complexity.
 
=== YOUR CORE TASK ===
Given an input image of a clay/play-dough figure, you must:
 
1. ANALYZE the figure thoroughly:
   - Identify the subject (animal, object, character)
   - Break down its PHYSICAL COMPONENTS (body parts, shapes, colors, textures)
   - Determine the CONSTRUCTION ORDER — how a human would logically build it
     piece by piece (base shapes first → assembly → details → final touches)
   - Note the FINISH (matte, glossy, satin) and surface quality
   - Identify the SURFACE/BACKGROUND the figure sits on
   - Note the CAMERA ANGLE of the reference photo
 
2. DETERMINE THE STEP COUNT using the complexity analysis below.
 
3. DECOMPOSE into that many sequential build steps.
 
4. CALCULATE the optimal grid layout for that step count.
 
5. OUTPUT a fully formatted prompt following the template structure below.
 
=== COMPLEXITY → STEP COUNT RULES ===
 
You MUST follow this mandatory counting procedure. Do NOT skip it. Do NOT eyeball
the step count. Count explicitly.
 
MANDATORY COUNTING PROCEDURE — FOLLOW EVERY TIME:
 
  Start with count = 0. Walk through the figure from raw clay to finished product
  and increment the count for EACH of the following that applies:
 
  PHASE A — BASE SHAPE OPERATIONS (count EACH transformation separately):
  +1 for rolling the initial ball or cylinder of clay
  +1 for EACH major shape transformation (ball → flat disc, disc → star, cylinder → coil, etc.)
      A "major shape transformation" = the overall silhouette changes.
      CRITICAL: "Roll a ball" and "Flatten into disc" are TWO separate steps, not one.
      CRITICAL: "Flatten into disc" and "Shape into star" are TWO separate steps, not one.
      You must NEVER skip the intermediate shapes. If the final form is a star, the
      progression is: ball → disc → star = 3 steps minimum for the base shape alone.
 
  PHASE B — SECONDARY PIECES (count EACH piece or batch):
  +1 for EACH separate piece that must be made (e.g., a head ball, a set of tentacle balls)
  +1 for EACH assembly/attachment action (e.g., attaching head to body)
 
  PHASE C — DETAIL OPERATIONS (count EACH category as a SEPARATE step):
  +1 for adding eye bases (white balls or circles) — this is its OWN step
  +1 for adding pupils (black dots on eyes) — this is its OWN step, SEPARATE from eyes
  +1 for carving/scoring any feature with a tool (smile, wing line, texture)
      → The tool must be visible lying beside the figure in this panel
  +1 for adding surface patterns (spots, stripes, dots — all of one type = 1 step)
  +1 for EACH additional accessory or appendage category (ears, tail, hat, bow, etc.)
 
  IMPORTANT — EYES AND PUPILS ARE ALWAYS SEPARATE STEPS:
  If the figure has eyes with pupils (white circles + black dots), this is ALWAYS
  2 steps, never 1. Step N: add white eye balls (pupils NOT YET PRESENT). Step N+1:
  add black pupils to the eyes. This split is MANDATORY because the image model will
  add pupils prematurely if they're in the same step as the eyes.
 
  IMPORTANT — SMILE/MOUTH IS ALWAYS ITS OWN STEP:
  A carved smile, mouth, or any facial expression line is ALWAYS its own dedicated step,
  never combined with eyes or pupils. The tool used to carve it must be visible.
 
  PHASE D — HERO SHOT (always):
  +1 for the final hero shot panel (ALWAYS the last step, ALWAYS included)
 
  FINAL COUNT = total from phases A + B + C + D
 
STEP COUNT BOUNDARIES:
  - Minimum: 4 steps (a truly minimal figure: roll shape → add one detail → hero shot)
  - Maximum: 12 steps (beyond this, panels get too small; group minor details if needed)
  - If your count lands between 4 and 12, USE THAT EXACT COUNT — do not round or compress
  - If your count exceeds 12, merge the LEAST important detail steps (never merge shape steps)
  - If your count is below 4, you missed steps — recount
 
ANTI-COMPRESSION RULES (READ CAREFULLY):
  - NEVER combine "roll ball" + "flatten" into one step — these are 2 steps
  - NEVER combine "flatten disc" + "shape into star/animal" into one step — these are 2 steps
  - NEVER combine "add eyes" + "add pupils" into one step — these are 2 steps
  - NEVER combine "add pupils" + "carve smile" into one step — these are 2 steps
  - NEVER combine "add pattern/spots" + "carve features" into one step — these are 2 steps
  - NEVER skip the ball stage. Every clay figure starts as a ball of clay. Panel 1 is
    ALWAYS a ball (or cylinder, or basic rolled shape). Never start with a finished shape.
  - NEVER skip intermediate shapes. If the final form requires ball → disc → star,
    you need 3 panels for the shape alone. You cannot jump from ball to star.
  - If you find yourself writing a panel where TWO things change from the previous panel,
    STOP and split it into two panels.
 
=== GRID LAYOUT CALCULATION ===
 
Based on the step count, determine the poster grid layout:
 
  4 steps  → 1 row of 4 panels                    | size: "1536x640"
  5 steps  → Row 1: 3, Row 2: 2 (centered)        | size: "1536x1024"
  6 steps  → 2 rows of 3 panels                   | size: "1536x1024"
  7 steps  → Row 1: 4, Row 2: 3 (centered)        | size: "1536x1024"
  8 steps  → 2 rows of 4 panels                   | size: "1536x1024"
  9 steps  → Row 1: 5, Row 2: 4 (centered)        | size: "1536x1024"
  10 steps → 2 rows of 5 panels                   | size: "1536x1024"
  11 steps → Row 1: 4, Row 2: 4, Row 3: 3 (centered) | size: "1536x1536"
  12 steps → 3 rows of 4 panels                   | size: "1536x1536"
 
Include the grid description AND the recommended image size in your output.
 
=== ANALYSIS RULES ===
 
COLOR EXTRACTION:
- Identify every distinct color in the figure
- Assign a closest hex code to each color
- Use the PRIMARY color of the figure as the poster's accent color
- Describe colors with natural names AND hex codes (e.g., "mint-green (#77DD77)")
 
CONSTRUCTION ORDER LOGIC:
- Largest/base pieces are ALWAYS made first
- Pieces are shown SEPARATE before assembly
- Assembly happens BEFORE any surface details
- Surface details (eyes, spots, stripes, patterns) are added ONE category at a time
- A TOOL step should be included if the figure has any carved/scored/indented features
  (smiles, lines, textures) — show the tool lying beside the figure
- The FINAL panel ALWAYS removes any tools, tightens the crop, and adds 1-2 colorful
  background props
 
INCREMENTAL CONSTRAINT (CRITICAL):
For EVERY panel (except Panel 1), you must specify THREE things:
  a) SHOW: What is visible in this panel
  b) NOT YET PRESENT: What must be COMPLETELY ABSENT
  c) VISUAL DIFFERENCE FROM PREVIOUS PANEL: The ONE key change
 
For Panel 1, specify only SHOW, NOT YET PRESENT, and CAPTION (no previous panel exists).
 
This triple-constraint prevents the image model from "jumping ahead" and adding
features too early.
 
=== STEP STRUCTURE PATTERN ===
 
Regardless of step count, the sequence must follow this arc:
 
  PHASE 1 — BASE SHAPES (first ~25-30% of steps):
    Making the individual clay pieces (balls, cylinders, cones, discs).
    Pieces are shown loose/separate on the surface.
 
  PHASE 2 — ASSEMBLY (next ~20-30% of steps):
    Joining pieces together. Major structural shaping.
    The recognizable form of the subject emerges here.
 
  PHASE 3 — DETAILS (next ~30-40% of steps):
    Adding features one category at a time: eyes, then mouth, then patterns,
    then accessories. Each detail category = one step.
    If any feature requires a TOOL (carving, scoring), show the tool in
    that panel and remove it in the next.
 
  PHASE 4 — HERO SHOT (always the LAST step):
    Final reveal. Tool removed. Tighter crop. 1-2 colorful clay props at edges.
    Celebratory "ta-da!" framing.
 
=== OUTPUT TEMPLATE ===
 
You must output ONLY a valid Python string (triple-quoted) containing the complete
image generation prompt. Follow this EXACT structure — adapt the panel count dynamically:
 
```
prompt = \"\"\"
Generate a single instructional poster image showing how to make a cute clay
[SUBJECT] character in [N] sequential steps, arranged as a grid of [N] panels.
 
=== POSTER LAYOUT ===
- Grid: [GRID DESCRIPTION based on step count, e.g., "Row 1 = 4 panels, Row 2 = 3
  panels (centered)"].
- Each panel is a square with a thin white border.
- Each panel has a step number badge top-left ("Step 1"..."Step [N]") in bold white text
  on a [ACCENT COLOR NAME] ([ACCENT HEX]) rounded badge.
- Each panel has a caption in white sans-serif text at the bottom over a semi-transparent
  dark strip.
- Poster background: [BACKGROUND COLOR AND HEX].
- Title at top: "HOW TO MAKE A CUTE CLAY [SUBJECT UPPERCASE]" in large bold
  [TITLE TEXT COLOR] text with a thin [ACCENT COLOR NAME] underline.
- All panels are photorealistic — [FINISH DESCRIPTION] polymer/play-dough clay on a
  [SURFACE DESCRIPTION AND COLOR], [LIGHTING DESCRIPTION], [CAMERA ANGLE], no human hands.
 
=== EXTREMELY IMPORTANT — READ BEFORE GENERATING ===
Each panel must show ONLY what has been added UP TO that step. Do NOT skip ahead.
The [SUBJECT] gets its features ONE AT A TIME across panels. If a feature is listed
under "NOT YET PRESENT," it must be COMPLETELY ABSENT from that panel — no [LIST KEY
FEATURES] until the specific step that adds them.
 
=== PANEL 1 — "[STEP 1 TITLE]" ===
SHOW: [Detailed description of what to show]
NOT YET PRESENT: [Everything not yet built]
CAPTION: "[Instruction text]"
 
=== PANEL 2 — "[STEP 2 TITLE]" ===
SHOW: [Detailed description]
NOT YET PRESENT: [Everything not yet built]
VISUAL DIFFERENCE FROM PANEL 1: [The ONE key change]
CAPTION: "[Instruction text]"
 
[...continue for ALL N panels, including the final hero shot...]
 
=== FINAL CHECKLIST — VERIFY BEFORE OUTPUT ===
Panel 1: [Expected state]. Nothing else.
Panel 2: [Expected state].
[...one line per panel...]
Panel [N]: [Expected state — hero shot].
 
If Panel [X] has [premature feature] → WRONG. Redo.
[...list critical validation rules, at least 1 per 2 panels...]
\"\"\"
```
 
IMPORTANT: Also output the recommended image size as a comment ABOVE the prompt string:
```
# Recommended size: "1536x1024"
prompt = \"\"\"...\"\"\"
```
 
=== QUALITY RULES ===
 
1. DESCRIPTIONS must be hyper-specific:
   - BAD: "a red ball"
   - GOOD: "A single smooth, perfectly round ball of matte coral-red polymer clay (~3 cm)
     sitting alone on the cream surface with a soft matte finish"
 
2. SIZES must be approximate but concrete (use cm or mm)
 
3. CAPTIONS must be short, instructional, present tense, imperative mood:
   - BAD: "Now you should put the eyes on"
   - GOOD: "Press two tiny black clay balls into the face as round bead eyes."
 
4. The NOT YET PRESENT section must EXHAUSTIVELY list every feature that hasn't appeared yet.
   Be paranoid about this — the image model WILL try to add features early.
 
5. VISUAL DIFFERENCE lines must name exactly ONE change (or two if a tool appears/disappears
   alongside a feature). Never describe more changes than actually happened.
 
6. The final hero shot panel must:
   - Remove any tools from the previous panel
   - Tighten the crop
   - Add 1-2 thematically appropriate colorful clay props at the edges
   - Feel like a "ta-da!" reveal moment
 
7. The FINAL CHECKLIST must include at least 1 "If Panel X has Y → WRONG. Redo." rule
   per every 2 panels, targeting the most likely model mistakes (premature eyes, premature
   mouth, premature patterns, etc.).
 
8. Match the CAMERA ANGLE to the subject:
   - Top-down (~75°): flat figures (starfish, cookies, coasters)
   - Front-facing (~30-35°): upright figures (animals, characters)
   - Three-quarter (~45°): medium-height figures
 
=== COMPLEXITY EXAMPLES (for calibration) ===
 
EXAMPLE A — Simple snake (5 steps):
  Components: green cylinder body, coiled shape, 2 black dot eyes, red forked tongue
  Counting: roll cylinder (+1) → coil into spiral (+1) → add black dot eyes (+1) →
            add red tongue (+1) → hero shot (+1) = 5 steps
  Steps: 1) Roll cylinder → 2) Coil into spiral → 3) Add eyes → 4) Add tongue →
         5) Hero shot
  Grid: Row 1: 3, Row 2: 2 (centered)
 
EXAMPLE B — Starfish (7 steps):
  Components: red ball → flat disc → star shape, white eye balls, black pupils, carved smile
  Counting: roll ball (+1) → flatten to disc (+1) → shape into star (+1) → add white
            eye balls (+1) → add black pupils (+1) → carve smile with tool (+1) →
            hero shot (+1) = 7 steps
  Steps: 1) Roll red ball → 2) Flatten into disc → 3) Shape into star → 4) Add white eyes →
         5) Add black pupils → 6) Carve smile (tool visible) → 7) Hero shot
  Grid: Row 1: 4, Row 2: 3
  NOTE: Panel 1 is JUST a ball. Panel 2 is JUST a disc. Panel 3 is the star with
        BLANK face (no eyes). Panel 4 has white eyes with NO pupils. This granularity
        is MANDATORY.
 
EXAMPLE C — Ladybug (7 steps):
  Components: red dome body, black head, white+black eyes, wing line, black spots
  Counting: roll red dome (+1) → make black head ball (+1) → attach head (+1) →
            add white eyes with black pupils (+1, simple enough to combine) →
            score wing line with tool (+1) → add spots (+1) → hero shot (+1) = 7 steps
  Steps: 1) Roll red dome → 2) Make black head ball → 3) Attach head → 4) Add eyes →
         5) Score wing line (with tool) → 6) Add spots → 7) Hero shot
  Grid: Row 1: 4, Row 2: 3
 
EXAMPLE D — Detailed owl (10 steps):
  Components: brown body, beige belly patch, 2 large white eyes, black pupils,
              orange beak, 2 small ears, wing feather texture, 2 orange feet
  Counting: roll brown body ball (+1) → flatten beige belly disc (+1) → attach belly
            to body (+1) → add white eye circles (+1) → add black pupils (+1) →
            attach orange beak (+1) → pinch ear tufts (+1) → score wing feather lines
            with tool (+1) → add orange feet (+1) → hero shot (+1) = 10 steps
  Steps: 1) Roll brown body ball → 2) Flatten beige belly disc → 3) Attach belly →
         4) Add white eye circles → 5) Add black pupils → 6) Attach beak →
         7) Pinch ear tufts → 8) Score feather lines (with tool) → 9) Add feet →
         10) Hero shot
  Grid: 2 rows of 5
 
EXAMPLE E — Dragon with accessories (12 steps):
  Components: green body, 4 legs, tail, white belly, head shape, yellow horns,
              white+black eyes, nostrils, red spikes down back, tiny wings
  Counting: roll green body (+1) → shape 4 legs + tail (+1) → attach legs + tail (+1) →
            shape head with snout (+1) → attach head to body (+1) → add white belly
            patch (+1) → add eyes (white + black) (+1) → add yellow horns (+1) →
            score nostrils with tool (+1) → add red spikes (+1) → add tiny wings (+1) →
            hero shot (+1) = 12 steps
  Steps: 1) Roll green body → 2) Shape legs + tail → 3) Attach legs + tail →
         4) Shape head → 5) Attach head → 6) Add belly patch → 7) Add eyes →
         8) Add horns → 9) Score nostrils (with tool) → 10) Add spikes →
         11) Add wings → 12) Hero shot
  Grid: 3 rows of 4
 
=== WHAT YOU MUST NEVER DO ===
- Never output explanation text — only the comment line with size + the prompt string
- Never default to any fixed step count — ALWAYS count explicitly using the procedure above
- Never add steps that aren't visible changes (no "let it dry" or "think about colors")
- Never combine two major additions in one panel
- Never forget the NOT YET PRESENT section for any panel
- Never use vague language ("some," "a few," "maybe") — be exact
- Never make the final hero panel identical to the previous panel — it MUST have visual differences
- Never exceed 12 steps — if the figure is very complex, group minor details together
- Never go below 4 steps — even the simplest figure needs: shape → detail → hero shot
 
=== COMMON MISTAKES TO AVOID (CRITICAL) ===
 
MISTAKE 1 — SKIPPING THE BALL STAGE:
  WRONG: Panel 1 shows a finished star shape
  RIGHT: Panel 1 shows a round ball → Panel 2 shows a flat disc → Panel 3 shows a star
  RULE: Every figure starts as a ball or cylinder. The first panel is ALWAYS raw rolled clay.
 
MISTAKE 2 — JUMPING FROM BALL TO FINAL SHAPE:
  WRONG: Panel 1 = ball, Panel 2 = star (skipped disc)
  RIGHT: Panel 1 = ball, Panel 2 = disc, Panel 3 = star
  RULE: Include EVERY intermediate shape transformation.
 
MISTAKE 3 — COMBINING EYES + PUPILS IN ONE STEP:
  WRONG: "Add white eyes with black pupils" as a single panel
  RIGHT: Panel N = white eye balls (NO pupils), Panel N+1 = add black pupils
  RULE: Eyes and pupils are ALWAYS separate steps.
 
MISTAKE 4 — COMBINING PUPILS + SMILE IN ONE STEP:
  WRONG: "Add pupils and carve a smile" as a single panel
  RIGHT: Panel N = add pupils (NO smile), Panel N+1 = carve smile (tool visible)
  RULE: Each facial feature category is its own step.
 
MISTAKE 5 — COMPRESSING TO FEWER PANELS TO "SIMPLIFY":
  WRONG: Reducing a 7-step figure to 4 steps because "it's simple"
  RIGHT: Count the actual operations and use that count
  RULE: The step count comes from COUNTING, not from a subjective "simple/complex" judgment.
 
MISTAKE 6 — WRITING THIN DESCRIPTIONS:
  WRONG: "A red star on a gray surface."
  RIGHT: "A five-pointed star with ROUNDED, CHUBBY, soft arms — like a cute cartoon
          starfish (~6 cm wide, ~0.5 cm thick). Center is slightly domed. Subtle finger-pinch
          texture on the arms. Matte coral-red (#E63946) clay on a dark grey (#4A4A4A) surface."
  RULE: Every panel description must be 3-5 sentences with sizes, textures, and specific visual details.
"""
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# USER PROMPT — This is appended with the image
# ═══════════════════════════════════════════════════════════════════════════════
 
USER_PROMPT = """
Analyze the attached image of a clay/play-dough figure carefully.
 
STEP 1 — Study every detail:
- What is the subject?
- What are ALL the distinct physical components (body parts, shapes)?
- What colors are used? (provide hex codes)
- What is the surface finish (matte, glossy, satin)?
- What is the background/surface it sits on?
- What is the camera angle?
 
STEP 2 — Count operations explicitly using the MANDATORY COUNTING PROCEDURE:
Walk through the build from raw clay to finished figure. For each operation, write:
  "+1 [operation name]"
and keep a running total. Include EVERY intermediate shape (ball → disc → star = 3 ops,
not 1). Eyes and pupils are ALWAYS 2 separate operations. Smile/mouth is ALWAYS its own
operation. The hero shot is ALWAYS +1 at the end.
 
Example counting for a starfish:
  +1 roll ball
  +1 flatten into disc
  +1 shape disc into star
  +1 add white eye balls (no pupils yet)
  +1 add black pupils to eyes
  +1 carve smile with tool
  +1 hero shot
  Total: 7 steps
 
STEP 3 — Determine the grid layout based on your step count.
 
STEP 4 — Generate the complete gpt-image-1.5 instructional poster prompt following
the exact template structure from your instructions.
 
VALIDATION — Before outputting, check:
  - Does Panel 1 show ONLY a ball/cylinder of clay? (not a finished shape)
  - Does each panel change EXACTLY ONE thing from the previous panel?
  - Are eyes and pupils in SEPARATE panels?
  - Is the smile/mouth in its OWN panel (not combined with eyes or pupils)?
  - Does every panel have SHOW, NOT YET PRESENT, and VISUAL DIFFERENCE sections?
  - Is the final panel a hero shot (tighter crop, props at edges, tool removed)?
  If any check fails, fix it before outputting.
 
Output format — output ONLY these three things in order:
1. Your counting work (each +1 line and the total)
2. A comment line: # Recommended size: "WxH"
3. The prompt as a Python triple-quoted string
 
No other explanation, no commentary, no markdown code fences.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# STREAMLIT CONFIG & PREMIUM UI
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="ClayMagic — AI Poster Generator",
    page_icon="🏺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&family=Poppins:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ═══════════════════════════════════════════════
   CSS CUSTOM PROPERTIES — PREMIUM DARK PALETTE
   ═══════════════════════════════════════════════ */
:root {
    --bg-deep:        #0F0F1A;
    --bg-surface:     #1A1A2E;
    --bg-card:        rgba(30, 30, 52, 0.72);
    --bg-card-solid:  #1E1E34;
    --glass-border:   rgba(255, 255, 255, 0.08);
    --glass-shine:    rgba(255, 255, 255, 0.04);

    --text-primary:   #F0EDF6;
    --text-secondary: #A8A3B8;
    --text-muted:     #6B6680;

    --accent-coral:   #FF6B6B;
    --accent-amber:   #FFBE45;
    --accent-mint:    #3EDDC2;
    --accent-sky:     #45B7D1;
    --accent-violet:  #A78BFA;

    --glow-coral:     rgba(255, 107, 107, 0.35);
    --glow-amber:     rgba(255, 190, 69, 0.30);
    --glow-mint:      rgba(62, 221, 194, 0.30);

    --radius-sm:  12px;
    --radius-md:  20px;
    --radius-lg:  28px;
    --radius-xl:  40px;
}

/* ═══════════════════════════════════════
   GLOBAL BACKGROUND — DEEP DARK MESH
   ═══════════════════════════════════════ */
.stApp {
    background:
        radial-gradient(ellipse 60% 50% at 15% 20%, rgba(167,139,250,0.12) 0%, transparent 70%),
        radial-gradient(ellipse 50% 40% at 85% 75%, rgba(255,107,107,0.08) 0%, transparent 65%),
        radial-gradient(ellipse 45% 55% at 50% 50%, rgba(62,221,194,0.06) 0%, transparent 60%),
        var(--bg-deep) !important;
    font-family: 'Poppins', sans-serif !important;
    color: var(--text-primary) !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* Override all Streamlit text to be light */
.stApp p, .stApp span, .stApp label, .stApp div,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stCaptionContainer"] span {
    color: var(--text-secondary) !important;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    color: var(--text-primary) !important;
    font-family: 'Fredoka', sans-serif !important;
}

/* Fix Streamlit's default hr */
.stApp hr {
    border-color: var(--glass-border) !important;
    margin: 1.5rem 0 !important;
}

/* ═══════════════════════════════════════
   HERO HEADER
   ═══════════════════════════════════════ */
.hero-header {
    text-align: center;
    padding: 2.5rem 1rem 1rem;
    position: relative;
}
.hero-badge {
    display: inline-block;
    background: var(--bg-card);
    border: 1px solid var(--glass-border);
    border-radius: 50px;
    padding: 6px 18px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 500;
    color: var(--accent-mint);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 1rem;
    backdrop-filter: blur(12px);
}
.hero-title {
    font-family: 'Fredoka', sans-serif !important;
    font-size: 3.4rem;
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: -1.5px;
    margin: 0;
    padding: 0;
    background: linear-gradient(135deg, #FFFFFF 0%, #F0EDF6 30%, var(--accent-amber) 60%, var(--accent-coral) 100%);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: title-shimmer 6s ease infinite;
}
@keyframes title-shimmer {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
}
.hero-sub {
    font-family: 'Poppins', sans-serif;
    font-size: 1.05rem;
    color: var(--text-secondary) !important;
    margin-top: 0.6rem;
    font-weight: 400;
    letter-spacing: 0.2px;
}
.hero-sub strong {
    color: var(--text-primary) !important;
    font-weight: 600;
}

/* ═══════════════════════════════════════
   PIPELINE CARDS — GLASSMORPHISM
   ═══════════════════════════════════════ */
.pipe-row {
    display: flex;
    gap: 1.2rem;
    max-width: 960px;
    margin: 1.5rem auto 0;
    padding: 0 1rem;
}
.pipe-card {
    flex: 1;
    background: var(--bg-card);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 1.6rem 1.4rem;
    position: relative;
    overflow: hidden;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.pipe-card:hover {
    transform: translateY(-4px);
}
.pipe-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: var(--radius-md) var(--radius-md) 0 0;
}
.pipe-card.s1::before { background: linear-gradient(90deg, var(--accent-coral), var(--accent-amber)); }
.pipe-card.s2::before { background: linear-gradient(90deg, var(--accent-sky), var(--accent-violet)); }
.pipe-card.s3::before { background: linear-gradient(90deg, var(--accent-mint), var(--accent-sky)); }
.pipe-card.s1:hover { box-shadow: 0 8px 32px var(--glow-coral); }
.pipe-card.s2:hover { box-shadow: 0 8px 32px rgba(69,183,209,0.25); }
.pipe-card.s3:hover { box-shadow: 0 8px 32px var(--glow-mint); }
.pipe-num {
    font-family: 'Fredoka', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 0.5rem;
}
.pipe-card.s1 .pipe-num { color: var(--accent-coral); }
.pipe-card.s2 .pipe-num { color: var(--accent-sky); }
.pipe-card.s3 .pipe-num { color: var(--accent-mint); }
.pipe-card h4 {
    font-family: 'Fredoka', sans-serif !important;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary) !important;
    margin: 0 0 0.35rem 0;
}
.pipe-card p {
    font-size: 0.85rem;
    color: var(--text-secondary) !important;
    margin: 0;
    line-height: 1.55;
    font-weight: 400;
}

/* ═══════════════════════════════════════
   SECTION HEADINGS (in-page)
   ═══════════════════════════════════════ */
.section-label {
    font-family: 'Fredoka', sans-serif;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.section-label .dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
}
.dot-coral  { background: var(--accent-coral); box-shadow: 0 0 8px var(--glow-coral); }
.dot-mint   { background: var(--accent-mint);  box-shadow: 0 0 8px var(--glow-mint);  }

/* ═══════════════════════════════════════
   UPLOAD / PLACEHOLDER ZONES
   ═══════════════════════════════════════ */
.drop-zone {
    background: var(--bg-card);
    backdrop-filter: blur(16px);
    border: 2px dashed rgba(167,139,250,0.35);
    border-radius: var(--radius-lg);
    padding: 3rem 2rem;
    text-align: center;
    transition: all 0.35s ease;
    max-width: 520px;
    margin: 0 auto;
}
.drop-zone:hover {
    border-color: var(--accent-violet);
    box-shadow: 0 0 30px rgba(167,139,250,0.15);
    transform: translateY(-3px);
}
.drop-icon {
    font-size: 3rem;
    margin-bottom: 0.6rem;
    display: block;
    animation: float 3s ease-in-out infinite;
}
@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}
.drop-label {
    font-family: 'Fredoka', sans-serif;
    font-size: 1.2rem;
    font-weight: 600;
    color: var(--text-primary);
}
.drop-sub {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.3rem;
}

/* Poster placeholder */
.poster-placeholder {
    background: var(--bg-card);
    backdrop-filter: blur(16px);
    border: 2px dashed rgba(62,221,194,0.30);
    border-radius: var(--radius-lg);
    padding: 3rem 2rem;
    text-align: center;
    min-height: 320px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    max-width: 520px;
    margin: 0 auto;
    transition: all 0.35s ease;
}
.poster-placeholder:hover {
    border-color: var(--accent-mint);
    box-shadow: 0 0 30px var(--glow-mint);
}

/* ═══════════════════════════════════════
   STREAMLIT FILE UPLOADER OVERRIDE
   ═══════════════════════════════════════ */
[data-testid="stFileUploader"] { max-width: 520px; margin: 0 auto; }
[data-testid="stFileUploader"] section {
    border: 2px dashed rgba(167,139,250,0.35) !important;
    border-radius: var(--radius-md) !important;
    background: var(--bg-card) !important;
    padding: 1.5rem !important;
    transition: border-color 0.3s ease !important;
}
[data-testid="stFileUploader"] section:hover {
    border-color: var(--accent-violet) !important;
}
[data-testid="stFileUploader"] section * {
    color: var(--text-secondary) !important;
}
[data-testid="stFileUploader"] button {
    background: var(--bg-surface) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 10px !important;
}

/* ═══════════════════════════════════════
   PREVIEW IMAGE CONTAINER
   ═══════════════════════════════════════ */
.preview-wrap {
    max-width: 380px;
    margin: 0 auto;
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 2px solid rgba(167,139,250,0.25);
    box-shadow: 0 8px 32px rgba(0,0,0,0.40);
}

/* ═══════════════════════════════════════
   RESULT FRAME — GRADIENT BORDER
   ═══════════════════════════════════════ */
.result-frame {
    background: var(--bg-card-solid);
    border-radius: var(--radius-lg);
    padding: 1rem;
    position: relative;
    max-width: 680px;
    margin: 0 auto;
    /* Gradient border trick */
    border: 3px solid transparent;
    background-image:
        linear-gradient(var(--bg-card-solid), var(--bg-card-solid)),
        linear-gradient(135deg, var(--accent-coral), var(--accent-amber), var(--accent-mint), var(--accent-sky));
    background-origin: border-box;
    background-clip: padding-box, border-box;
    box-shadow:
        0 12px 48px rgba(0,0,0,0.50),
        0 0 60px rgba(255,190,69,0.08);
}
.result-frame img {
    border-radius: var(--radius-md);
    width: 100%;
}

/* ═══════════════════════════════════════
   GENERATE BUTTON — GLOWING CTA
   ═══════════════════════════════════════ */
.stButton > button {
    background: var(--bg-card) !important;
    color: var(--accent-amber) !important;
    font-family: 'Fredoka', sans-serif !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    padding: 0.85rem 2.8rem !important;
    border: 1px solid var(--accent-amber) !important;
    border-radius: var(--radius-xl) !important;
    box-shadow: 0 0 16px var(--glow-amber) !important;
    transition: all 0.3s ease !important;
    letter-spacing: 0.5px !important;
    display: block !important;
    margin: 0 auto !important;
    cursor: pointer !important;
}
.stButton > button:hover {
    background: var(--accent-amber) !important;
    color: var(--bg-deep) !important;
    box-shadow: 0 0 32px var(--glow-amber) !important;
    transform: translateY(-2px) !important;
}
.stButton > button:active {
    transform: translateY(-1px) scale(1.01) !important;
}

/* Download button style */
.stDownloadButton > button {
    background: var(--bg-card) !important;
    color: var(--accent-mint) !important;
    font-family: 'Fredoka', sans-serif !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    padding: 0.65rem 2rem !important;
    border: 1px solid var(--accent-mint) !important;
    border-radius: var(--radius-xl) !important;
    box-shadow: 0 0 16px var(--glow-mint) !important;
    transition: all 0.3s ease !important;
    display: block !important;
    margin: 0.8rem auto 0 !important;
}
.stDownloadButton > button:hover {
    background: var(--accent-mint) !important;
    color: var(--bg-deep) !important;
    box-shadow: 0 0 32px var(--glow-mint) !important;
    transform: translateY(-2px) !important;
}

/* ═══════════════════════════════════════
   PROGRESS BAR — NEON GLOW
   ═══════════════════════════════════════ */
.progress-wrapper {
    max-width: 640px;
    margin: 2rem auto;
    padding: 0 1rem;
}
.progress-outer {
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--glass-border);
    border-radius: 50px;
    height: 36px;
    overflow: hidden;
    position: relative;
}
.progress-inner {
    height: 100%;
    border-radius: 50px;
    background: linear-gradient(90deg,
        var(--accent-coral),
        var(--accent-amber),
        var(--accent-mint),
        var(--accent-sky),
        var(--accent-violet));
    background-size: 300% 100%;
    animation: neon-flow 2.5s ease-in-out infinite;
    transition: width 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 16px;
    min-width: 64px;
    box-shadow: 0 0 20px var(--glow-coral), 0 0 40px rgba(255,190,69,0.15);
}
@keyframes neon-flow {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.progress-pct {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--bg-deep);
    white-space: nowrap;
}
.progress-label {
    text-align: center;
    margin-top: 0.75rem;
    font-family: 'Poppins', sans-serif;
    font-size: 0.95rem;
    font-weight: 500;
    color: var(--text-secondary);
    min-height: 1.6rem;
}
.progress-complete .progress-inner {
    background: linear-gradient(90deg, var(--accent-mint), var(--accent-sky), var(--accent-mint));
    background-size: 300% 100%;
    animation: neon-flow 1.5s ease-in-out infinite;
    box-shadow: 0 0 24px var(--glow-mint), 0 0 48px rgba(62,221,194,0.2);
}

/* ═══════════════════════════════════════
   DIVIDER
   ═══════════════════════════════════════ */
.clay-divider {
    text-align: center;
    padding: 0.8rem 0;
    opacity: 0.35;
    letter-spacing: 12px;
    font-size: 0.9rem;
}

/* ═══════════════════════════════════════
   FOOTER
   ═══════════════════════════════════════ */
.footer-bar {
    text-align: center;
    padding: 1.5rem 1rem;
    margin-top: 1rem;
}
.footer-bar span {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--text-muted) !important;
    letter-spacing: 0.8px;
}
.footer-bar .ft-accent {
    color: var(--accent-amber) !important;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def encode_uploaded_image(uploaded_file) -> str:
    """Encode uploaded file to a data URI string."""
    mime = uploaded_file.type or "image/png"
    encoded = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def render_progress(pct: int, label: str, done: bool = False):
    """Render the custom neon progress bar."""
    done_class = "progress-complete" if done else ""
    return f"""
    <div class="progress-wrapper">
        <div class="progress-outer {done_class}">
            <div class="progress-inner" style="width: {max(pct, 5)}%;">
                <span class="progress-pct">{pct}%</span>
            </div>
        </div>
        <div class="progress-label">{label}</div>
    </div>
    """


def generate_prompt(image_data_uri: str) -> str:
    """
    Call Azure OpenAI o3 model using the chat.completions API
    to analyze the clay figure image and generate an image-generation prompt.
    """
    from openai import AzureOpenAI
    client = AzureOpenAI(
        azure_endpoint=GPT_NANO_ENDPOINT,
        api_key=GPT_NANO_API_KEY,
        api_version=GPT_NANO_API_VERSION,
    )
    response = client.chat.completions.create(
        model=GPT_NANO_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_uri,
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": USER_PROMPT,
                    },
                ],
            },
        ],
    )
    return response.choices[0].message.content


def extract_prompt_and_size(raw_output: str) -> tuple[str, str]:
    """
    Parse the raw o3 output to extract:
      1. The image-generation prompt (from the triple-quoted Python string)
      2. The recommended image size (from the comment line)
    Returns (poster_prompt, image_size).
    """
    size_match = re.search(r'# Recommended size:\s*"(\d+x\d+)"', raw_output)
    image_size = size_match.group(1) if size_match else "1536x1024"

    prompt_match = re.search(r'"""(.+?)"""', raw_output, re.DOTALL)
    poster_prompt = prompt_match.group(1).strip() if prompt_match else raw_output

    return poster_prompt, image_size


def generate_image(prompt_text: str, image_size: str = "1536x1024") -> Image.Image:
    """
    Call Azure OpenAI gpt-image-1.5 model to generate the poster image,
    passing the extracted image size.
    """
    from openai import AzureOpenAI
    client = AzureOpenAI(
        azure_endpoint=GPT_IMAGE_ENDPOINT,
        api_key=GPT_IMAGE_API_KEY,
        api_version=GPT_IMAGE_API_VERSION,
    )
    result = client.images.generate(
        model=GPT_IMAGE_MODEL,
        prompt=prompt_text,
        size=image_size,
    )
    image_bytes = base64.b64decode(result.data[0].b64_json)
    return Image.open(BytesIO(image_bytes))


# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT — HERO
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="hero-header">
    <div class="hero-badge">AI-Powered Clay Crafting</div>
    <h1 class="hero-title">ClayMagic Studio</h1>
    <p class="hero-sub">Upload any image — our AI deconstructs it into a <strong>step-by-step play-dough poster</strong> for kids</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="clay-divider">● ● ● ● ●</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT — PIPELINE CARDS
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="pipe-row">
    <div class="pipe-card s1">
        <div class="pipe-num">01</div>
        <h4>Upload Image</h4>
        <p>Drop any character, animal, or object — JPG, PNG, or WEBP. We handle the rest.</p>
    </div>
    <div class="pipe-card s2">
        <div class="pipe-num">02</div>
        <h4>AI Deconstruction</h4>
        <p>AI analyzes every shape, color, and texture — then writes a granular crafting sequence.</p>
    </div>
    <div class="pipe-card s3">
        <div class="pipe-num">03</div>
        <h4>Poster Rendered</h4>
        <p>AI generates a photorealistic, kid-friendly instruction poster in seconds.</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("")
st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT — TWO COLUMN: INPUT + OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.markdown("""
    <div class="section-label">
        <span class="dot dot-coral"></span> Your Input Image
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Drop your image here",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
    )
    if uploaded_file:
        img_preview = Image.open(uploaded_file)

        st.markdown(f"""
        <div class="drop-zone">
            <img src="data:{uploaded_file.type};base64,{base64.b64encode(uploaded_file.getvalue()).decode()}"
                style="max-width: 100%; max-height: 220px; border-radius: 12px; object-fit: contain; margin-bottom: 10px;" />
            <div class="drop-label">Image Uploaded</div>
            <div class="drop-sub">{uploaded_file.name}</div>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.markdown("""
        <div class="drop-zone">
            <span class="drop-icon">📸</span>
            <div class="drop-label">Your Input Image is displayed here</div>
        </div>
        """, unsafe_allow_html=True)

with right_col:
    st.markdown("""
    <div class="section-label">
        <span class="dot dot-mint"></span> Generated Poster
    </div>
    """, unsafe_allow_html=True)

    if "result_image" in st.session_state and st.session_state.result_image is not None:
        st.markdown('<div class="result-frame">', unsafe_allow_html=True)
        st.image(st.session_state.result_image, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)
        buf = BytesIO()
        st.session_state.result_image.save(buf, format="PNG")
        st.download_button(
            label="Download Poster",
            data=buf.getvalue(),
            file_name="playdough_poster.png",
            mime="image/png",
        )
    else:
        st.markdown("""
        <div class="poster-placeholder">
            <span class="drop-icon">🏺</span>
            <div class="drop-label" style="color: var(--accent-mint);">Your poster will appear here</div>
        </div>""", unsafe_allow_html=True)

st.markdown("")


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATION PIPELINE WITH ANIMATED PROGRESS
# ═══════════════════════════════════════════════════════════════════════════════

if uploaded_file:
    generate_clicked = st.button("Generate Poster")

    if generate_clicked:
        st.session_state.result_image = None

        progress_placeholder = st.empty()

        phase1_messages = [
            "Studying your image closely…",
            "Mapping shapes, colors, and anatomy…",
            "Measuring proportions and features…",
            "Understanding every detail…",
        ]
        phase2_messages = [
            "Writing step-by-step crafting instructions…",
            "Building the shape-then-place sequence…",
            "Checking visual continuity across steps…",
        ]
        phase3_messages = [
            "Mixing play-dough colors…",
            "Rendering step panels one by one…",
            "Shaping the poster layout…",
            "Adding clay texture and lighting…",
            "Polishing the final details…",
            "Almost there — finishing touches…",
        ]

        # ── Phase 1: Analyze image + generate prompt ──
        prompt_result = {"value": None, "error": None}

        def run_prompt_generation():
            try:
                uploaded_file.seek(0)
                image_data_uri = encode_uploaded_image(uploaded_file)
                prompt_result["value"] = generate_prompt(image_data_uri)
            except Exception as e:
                prompt_result["error"] = str(e)

        thread = threading.Thread(target=run_prompt_generation)
        thread.start()

        pct = 0
        msg_idx = 0
        all_phase1_msgs = phase1_messages + phase2_messages
        while thread.is_alive():
            if pct < 15:
                pct += 2
            elif pct < 30:
                pct += 1
            elif pct < 42:
                pct += 0.5
            elif pct < 48:
                pct += 0.2

            pct_int = min(int(pct), 48)
            current_msg = all_phase1_msgs[min(msg_idx, len(all_phase1_msgs) - 1)]
            progress_placeholder.markdown(render_progress(pct_int, current_msg), unsafe_allow_html=True)

            if pct_int % 8 == 0 and pct_int > 0:
                msg_idx = min(msg_idx + 1, len(all_phase1_msgs) - 1)

            time.sleep(0.4)

        thread.join()

        if prompt_result["error"]:
            progress_placeholder.markdown(
                render_progress(0, f"Prompt generation failed: {prompt_result['error']}"),
                unsafe_allow_html=True,
            )
            st.stop()

        raw_output = prompt_result["value"]

        # ── Extract poster prompt and image size from raw o3 output ──
        poster_prompt, image_size = extract_prompt_and_size(raw_output)

        # Log diagnostics to console
        counting_lines = [line for line in raw_output.split("\n") if line.strip().startswith("+1")]
        total_match = re.search(r"Total:\s*(\d+)", raw_output)
        counted_steps = int(total_match.group(1)) if total_match else len(counting_lines)
        panel_count = len(re.findall(r"=== PANEL \d+", poster_prompt))
        print(f"[ClayMagic] Counted steps: {counted_steps} | Detected panels: {panel_count} | Size: {image_size}")
        if panel_count != counted_steps:
            print(f"  WARNING: Panel count ({panel_count}) doesn't match counted steps ({counted_steps})!")

        progress_placeholder.markdown(
            render_progress(50, "Crafting instructions ready — now generating poster…"),
            unsafe_allow_html=True,
        )
        time.sleep(0.8)

        # ── Phase 2: Generate image ──
        image_result = {"value": None, "error": None}

        def run_image_generation():
            try:
                image_result["value"] = generate_image(poster_prompt, image_size)
            except Exception as e:
                image_result["error"] = str(e)

        thread2 = threading.Thread(target=run_image_generation)
        thread2.start()

        pct = 52
        msg_idx = 0
        while thread2.is_alive():
            if pct < 65:
                pct += 1.5
            elif pct < 78:
                pct += 0.8
            elif pct < 88:
                pct += 0.4
            elif pct < 95:
                pct += 0.15
            elif pct < 98:
                pct += 0.05
            else:
                pct = min(pct + 0.01, 99)

            pct_int = min(int(pct), 99)
            current_msg = phase3_messages[min(msg_idx, len(phase3_messages) - 1)]
            progress_placeholder.markdown(render_progress(pct_int, current_msg), unsafe_allow_html=True)

            if int(pct) % 10 == 0 and int(pct) > 52:
                msg_idx = min(msg_idx + 1, len(phase3_messages) - 1)

            time.sleep(0.5)

        thread2.join()

        if image_result["error"]:
            progress_placeholder.markdown(
                render_progress(min(int(pct), 99), f"Image generation failed: {image_result['error']}"),
                unsafe_allow_html=True,
            )
            st.stop()

        st.session_state.result_image = image_result["value"]

        progress_placeholder.markdown(
            render_progress(100, "Your poster is ready!", done=True),
            unsafe_allow_html=True,
        )
        time.sleep(1.2)

        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("""
<div class="footer-bar">
    <span>ClayMagic Studio — powered by <span class="ft-accent">AI</span>
</div>
""", unsafe_allow_html=True)
