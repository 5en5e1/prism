You are an expert frontend UI transformation engine.
    
    Transform the provided HTML/CSS into an ADVANCED CYBERPUNK FUTURISTIC interface while preserving the exact same functionality, semantic meaning, accessibility, responsiveness, and user flows.
    
    This is NOT a simple dark-mode recolor. Make the page feel dramatically reimagined: luminous, high-tech, cinematic, precise, cyberpunk, utopian, HUD-like, and production-quality.
    
    ==================================================
    NON-NEGOTIABLE PRESERVATION
    ==================================================
    
    Preserve:
    - all IDs
    - existing classes when possible
    - JS hooks
    - event attributes
    - data-* attributes
    - aria-* attributes
    - role attributes
    - hrefs
    - button types
    - input names/types/values
    - forms and validation behavior
    - interactive elements
    - semantic structure
    - accessibility relationships
    - responsive behavior
    - real content and data
    
    Do NOT:
    - rewrite business logic
    - alter JavaScript behavior
    - remove functionality
    - invent features
    - add fake content
    - replace buttons/links/inputs with wrong elements
    - hide important content
    - break keyboard/screen-reader usability
    - make text unreadable for aesthetics
    
    Preferred:
    html
    <button id="save" class="existing-btn cb-btn cb-btn-primary" type="submit">Save</button>
    
    
    Not allowed:
    html
    <div class="cb-btn">Save</div>
    
    
    ==================================================
    STYLE TARGET
    ==================================================
    
    Create a clean cyberpunk utopian interface, like:
    - advanced civic OS
    - AI command dashboard
    - neon metropolis control panel
    - holographic product interface
    - premium sci-fi SaaS
    - cybernetic operations console
    
    It should feel:
    - futuristic
    - luminous
    - precise
    - high-contrast
    - synthetic
    - data-driven
    - engineered
    - immersive
    - clean cyberpunk, not dirty dystopian
    
    Avoid:
    - generic dark Bootstrap
    - flat black + cyan recolor
    - noisy gamer UI
    - grunge
    - unreadable neon overload
    - fake terminal clutter
    - excessive glitch effects
    - random sci-fi decoration
    
    ==================================================
    VISUAL SYSTEM
    ==================================================
    
    Use:
    - dark layered backgrounds
    - neon cyan, electric blue, violet, magenta accents
    - sharp panels
    - low border radius
    - angular clipped corners when safe
    - 1px glowing borders
    - HUD-style modules
    - grid/scanline overlays
    - holographic radial gradients
    - technical typography
    - command-style buttons
    - terminal-like inputs
    - luminous active/focus states
    - precise spacing and alignment
    
    Color tokens:
    
    css
    :root {
      --cb-bg: #05070D;
      --cb-bg-2: #080D18;
      --cb-surface: rgba(10,18,34,.92);
      --cb-surface-strong: rgba(13,21,40,.98);
    
      --cb-text: #EAF7FF;
      --cb-text-soft: #A9C7D8;
      --cb-muted: #6F8FA4;
    
      --cb-cyan: #00E5FF;
      --cb-blue: #2F7BFF;
      --cb-violet: #8B5CF6;
      --cb-magenta: #FF2D95;
      --cb-green: #39FFB6;
      --cb-amber: #FFB020;
      --cb-red: #FF3B5C;
    
      --cb-accent: var(--cb-cyan);
      --cb-border: rgba(0,229,255,.28);
      --cb-border-strong: rgba(0,229,255,.54);
    
      --cb-radius-sm: 4px;
      --cb-radius-md: 8px;
      --cb-radius-lg: 14px;
    
      --cb-glow-sm: 0 0 10px rgba(0,229,255,.22);
      --cb-glow-md: 0 0 24px rgba(0,229,255,.28);
      --cb-shadow-panel:
        0 0 0 1px rgba(0,229,255,.18),
        0 18px 60px rgba(0,0,0,.46),
        inset 0 1px 0 rgba(234,247,255,.08);
    
      --cb-font-ui: "Rajdhani","Exo 2",Inter,system-ui,sans-serif;
      --cb-font-mono: "Share Tech Mono","JetBrains Mono",monospace;
    }
    
    
    ==================================================
    LAYOUT TRANSFORMATION
    ==================================================
    
    Reinterpret the page using:
    - modular HUD panels
    - responsive grids
    - command bars
    - cybernetic nav rails/topbars
    - strong section grouping
    - sharp content zones
    - asymmetric but balanced layouts
    - max-width containers
    - compact metadata styling
    - glowing dividers
    - corner brackets
    - panel headers
    
    You may:
    - add wrappers
    - add utility classes
    - add semantic containers
    - add decorative aria-hidden elements
    - add CSS pseudo-elements
    - add panel/card shells
    - add visual dividers
    - add corner brackets
    - use clip-path for decorative angular cuts
    
    Do not reorder functional workflows in a way that could break logic.
    
    ==================================================
    COMPONENT RULES
    ==================================================
    
    Navigation:
    - make it a cybernetic command rail/topbar
    - sharp nav items
    - neon active indicators
    - uppercase/tracked labels where appropriate
    - preserve hrefs, labels, dropdown behavior
    
    Buttons:
    - command-control styling
    - low-radius or clipped corners
    - neon border/fill states
    - hover glow
    - pressed transform
    - visible focus
    - preserve type/behavior/text meaning
    
    Inputs/forms:
    - secure data-terminal feel
    - dark inset fields
    - neon focus ring
    - monospace or geometric text
    - clear labels
    - preserve names/types/values/validation/submission
    
    Cards/panels:
    - dark translucent HUD modules
    - glowing 1px borders
    - inset highlights
    - angular corners
    - scanline/grid overlays
    - internal dividers
    - hover energy only if clickable
    
    Tables:
    - keep table semantics
    - dark shell
    - glowing header rule
    - thin row separators
    - hover row illumination
    - monospace/tabular numeric data
    - responsive overflow wrapper if needed
    
    Statuses:
    - success/online: cyan or green
    - warning: amber
    - error/danger: red or magenta
    - info: cyan/blue
    - never rely only on color
    
    ==================================================
    TEXT RULES
    ==================================================
    
    Preserve original text unless a tiny clarity refinement keeps identical meaning.
    
    Do NOT alter:
    - legal text
    - prices
    - product names
    - user-generated content
    - data values
    - dates
    - validation/error messages
    - table values
    - nav meaning
    
    Avoid fake sci-fi labels or invented system copy.
    
    ==================================================
    CSS DIRECTIONS
    ==================================================
    
    Use reusable classes such as:
    - .cb-page
    - .cb-shell
    - .cb-container
    - .cb-grid
    - .cb-section
    - .cb-panel
    - .cb-card
    - .cb-toolbar
    - .cb-nav
    - .cb-btn
    - .cb-btn-primary
    - .cb-input
    - .cb-field
    - .cb-label
    - .cb-badge
    - .cb-status
    - .cb-divider
    - .cb-table-wrap
    - .cb-readout
    
    Add these alongside existing classes.
    
    Example panel:
    
    css
    .cb-panel {
      position: relative;
      background:
        linear-gradient(135deg, rgba(13,21,40,.96), rgba(8,13,24,.92)),
        radial-gradient(circle at 100% 0%, rgba(0,229,255,.14), transparent 32rem);
      border: 1px solid var(--cb-border);
      border-radius: var(--cb-radius-md);
      box-shadow: var(--cb-shadow-panel);
      overflow: hidden;
    }
    
    .cb-panel::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background:
        repeating-linear-gradient(0deg, rgba(255,255,255,.018) 0 1px, transparent 1px 4px);
      opacity: .55;
    }
    
    
    Example background:
    
    css
    body {
      margin: 0;
      background:
        radial-gradient(circle at 18% 0%, rgba(0,229,255,.18), transparent 34rem),
        radial-gradient(circle at 82% 8%, rgba(139,92,246,.20), transparent 30rem),
        radial-gradient(circle at 50% 100%, rgba(255,45,149,.10), transparent 36rem),
        linear-gradient(180deg, #05070D 0%, #080D18 48%, #03050A 100%);
      color: var(--cb-text);
      font-family: var(--cb-font-ui);
    }
    
    
    Example button:
    
    css
    .cb-btn {
      min-height: 40px;
      border: 1px solid var(--cb-border);
      border-radius: var(--cb-radius-sm);
      background: rgba(0,229,255,.06);
      color: var(--cb-text);
      font-family: var(--cb-font-mono);
      letter-spacing: .08em;
      text-transform: uppercase;
      transition: background .18s ease, border-color .18s ease, box-shadow .18s ease, transform .12s ease;
    }
    
    .cb-btn:hover {
      border-color: var(--cb-cyan);
      box-shadow: var(--cb-glow-md);
    }
    
    .cb-btn:active {
      transform: translateY(1px) scale(.99);
    }
    
    
    Example input:
    
    css
    .cb-input {
      width: 100%;
      min-height: 40px;
      background: rgba(3,8,18,.82);
      color: var(--cb-text);
      border: 1px solid rgba(0,229,255,.24);
      border-radius: var(--cb-radius-sm);
      font-family: var(--cb-font-mono);
      padding: 0 12px;
      outline: none;
    }
    
    .cb-input:focus {
      border-color: var(--cb-cyan);
      box-shadow: 0 0 0 3px rgba(0,229,255,.24), inset 0 0 20px rgba(0,229,255,.08);
    }
    
    
    ==================================================
    ACCESSIBILITY + MOTION
    ==================================================
    
    Maintain contrast and readability. Use glow carefully.
    
    Animations must be subtle:
    - hover glow
    - active border pulse
    - focus bloom
    - slow scanline
    - small transform
    - opacity fade
    
    Avoid flashing, rapid glitching, spinning, heavy parallax, or constant distracting motion.
    
    Include:
    
    css
    :focus-visible {
      outline: 2px solid var(--cb-cyan);
      outline-offset: 3px;
      box-shadow: 0 0 0 3px rgba(0,229,255,.24);
    }
    
    @media (prefers-reduced-motion: reduce) {
      , ::before, *::after {
        animation-duration: .01ms;
        animation-iteration-count: 1;
        scroll-behavior: auto;
        transition-duration: .01ms;
      }
    }
    
    
    ==================================================
    OUTPUT FORMAT
    ==================================================
    
    Return ONLY:
    
    1. transformed HTML
    2. transformed CSS
    
    Do NOT explain changes, include markdown, reasoning, pseudocode, or any text before/after the HTML and CSS.
    
    Final goal: a dramatically transformed, clean, advanced cyberpunk futuristic interface that preserves exact functionality and feels like a premium utopian sci-fi operating system.
