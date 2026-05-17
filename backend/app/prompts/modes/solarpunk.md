==================================================
    LIVING SOLARPUNK / BIO-MECHANICAL DIRECTION
    ==================================================
    
    The redesign should feel more alive, utopian, and bio-mechanically integrated.
    
    Solarpunk here does not mean only plants, beige backgrounds, and green buttons.
    
    It should suggest a future where technology and nature are harmonized:
    
    * architecture grown with biology
    * interfaces that feel cultivated, not manufactured
    * soft machinery powered by sunlight
    * greenhouse-like structures
    * organic circuits
    * botanical patterns merged with technical systems
    * clean energy motifs
    * living materials
    * communal optimism
    * ecological abundance
    * calm advanced technology
    
    The interface should feel like it belongs in a hopeful ecological future.
    
    Do not modify the underlying structure, functionality, IDs, forms, JavaScript hooks, or interaction logic.
    
    You may only transform the visual presentation through HTML-safe wrappers, classes, decorative non-functional elements, and CSS.
    
    ==================================================
    VISUAL LANGUAGE: BIO-MECHANICAL SOLARPUNK
    ==================================================
    
    Use design cues that combine nature and soft technology:
    
    * vine-like connector lines
    * solar panel inspired grids
    * greenhouse frames
    * leaf-vein borders
    * root-network patterns
    * botanical circuit traces
    * seed-pod buttons
    * canopy-like section headers
    * sunlight halos
    * soft mechanical joints
    * terraced garden layers
    * translucent-but-warm material surfaces
    * living dashboard panels
    * organic data containers
    * circular solar motifs
    * flowing dividers that resemble stems, roots, or irrigation channels
    
    The page should feel designed by a civilization that builds with plants, sunlight, water, and elegant technology.
    
    Avoid making it look like:
    
    * fantasy forest UI
    * generic nature website
    * cyberpunk
    * sci-fi spaceship UI
    * neon hacker dashboard
    * sterile climate-tech SaaS
    * simple green recolor
    
    ==================================================
    UTOPIAN INTERFACE ELEMENTS
    ==================================================
    
    Where visually appropriate, introduce subtle utopian design elements:
    
    * sunrise gradients
    * soft abundance motifs
    * community-garden visual rhythm
    * optimistic status indicators
    * rounded greenhouse-like containers
    * solar-harvesting panel patterns
    * living-system ornamentation
    * gentle ecological symbols
    * warm civic/public-infrastructure feeling
    * peaceful high-tech environmental harmony
    
    The UI should feel public-spirited, humane, and optimistic rather than corporate.
    
    Think:
    
    * a dashboard inside a community greenhouse
    * civic technology grown into a garden wall
    * a clean energy control panel softened by living materials
    * a future public service interface powered by sunlight and ecology
    
    ==================================================
    STRUCTURE PRESERVATION HARD RULE
    ==================================================
    
    Do NOT structurally redesign the application.
    
    You must not:
    
    * change the order of functional sections
    * remove elements
    * replace interactive elements with different tags
    * alter form hierarchy
    * change JavaScript behavior
    * change IDs
    * remove classes used as hooks
    * move elements in ways that could break logic
    * invent new app features
    * add new functional controls
    * add fake content
    * change data meaning
    
    You may:
    
    * add purely decorative wrappers
    * add visual-only spans/divs with aria-hidden="true"
    * add CSS pseudo-elements
    * add classes
    * add section shells
    * add decorative separators
    * add non-interactive visual motifs
    * visually restyle existing components dramatically
    
    The DOM must remain functionally equivalent.
    
    ==================================================
    MAKE IT FEEL ALIVE WITHOUT CHANGING FUNCTIONALITY
    ==================================================
    
    Use CSS to make the page feel subtly alive:
    
    * gentle hover breathing
    * soft light shifts
    * organic shadow changes
    * calm focus bloom
    * subtle background gradient drift
    * slow solar glow on important panels
    * vine-like pseudo-element decorations
    * botanical circuit patterns in backgrounds
    * layered depth suggesting living infrastructure
    
    Motion must remain subtle and accessibility-safe.
    
    Do not use distracting animations, constant motion, spinning, flashing, aggressive parallax, or anything that harms usability.
    
    Always include reduced-motion support.
    
    ==================================================
    BIO-MECHANICAL BORDER SYSTEM
    ==================================================
    
    Borders should be a major part of the transformation.
    
    Avoid default plain borders.
    
    Use:
    
    * double organic borders
    * leaf-vein corner accents
    * soft solar-gradient outlines
    * inset greenhouse-frame borders
    * dotted seed-line borders
    * root-network separators
    * circuit-vine strokes
    * rounded mechanical-organic joints
    * warm inner highlights
    * layered card outlines
    
    Examples of acceptable CSS techniques:
    
    css
    .sp-card {
      position: relative;
      border: 1px solid rgba(88, 124, 76, 0.28);
      border-radius: 28px 36px 24px 40px;
      background:
        linear-gradient(145deg, rgba(255, 250, 232, 0.96), rgba(221, 235, 211, 0.92)),
        radial-gradient(circle at 12% 0%, rgba(236, 177, 82, 0.18), transparent 34%);
      box-shadow:
        0 18px 45px rgba(57, 82, 51, 0.14),
        inset 0 1px 0 rgba(255, 255, 255, 0.72);
    }
    
    .sp-card::before {
      content: "";
      position: absolute;
      inset: 10px;
      border-radius: inherit;
      border: 1px dashed rgba(96, 123, 75, 0.22);
      pointer-events: none;
    }
    
    .sp-card::after {
      content: "";
      position: absolute;
      right: 18px;
      top: 18px;
      width: 44px;
      height: 44px;
      border-radius: 999px;
      background:
        radial-gradient(circle, rgba(216, 168, 79, 0.35), transparent 62%),
        conic-gradient(from 180deg, rgba(96, 123, 75, 0.28), transparent, rgba(158, 201, 195, 0.3));
      pointer-events: none;
    }
    
    
    ==================================================
    BACKGROUND SYSTEM
    ==================================================
    
    The page background should feel like a living environmental system, not a flat canvas.
    
    Use layered CSS backgrounds such as:
    
    * soft sunrise gradients
    * faint botanical circuit patterns
    * solar grid lines
    * contour lines
    * warm paper texture
    * greenhouse-glass panels
    * leaf-shadow effects
    * radial sunlight pools
    
    Example direction:
    
    css
    body {
      background:
        radial-gradient(circle at 12% 8%, rgba(232, 177, 89, 0.24), transparent 30%),
        radial-gradient(circle at 88% 18%, rgba(150, 190, 144, 0.28), transparent 34%),
        linear-gradient(135deg, #fff7df 0%, #e9f0dc 46%, #d9ece7 100%);
      color: var(--sp-ink);
    }
    
    
    Add subtle patterning through pseudo-elements or container backgrounds, but do not interfere with readability.
    
    ==================================================
    BUTTONS AND CONTROLS
    ==================================================
    
    Buttons should feel like tactile ecological technology.
    
    They may resemble:
    
    * seed pods
    * solar toggles
    * soft ceramic controls
    * polished plant-based material
    * rounded civic kiosks
    * garden-interface controls
    
    Use:
    
    * pill shapes
    * warm gradient fills
    * soft mechanical borders
    * inset highlights
    * solar glows
    * gentle hover lift
    * visible focus rings
    * calm pressed states
    
    Do not change button text unless the meaning remains exactly the same.
    
    Do not change button type or behavior.
    
    ==================================================
    NAVIGATION
    ==================================================
    
    Navigation should feel like a garden path or greenhouse control rail.
    
    Use:
    
    * rounded pill nav items
    * soft active markers
    * vine-like separators
    * solar-tab indicators
    * warm background shells
    * subtle ecological icons only if decorative
    * calm hover states
    
    Do not change destination links, hrefs, labels, or menu behavior.
    
    ==================================================
    DATA, CARDS, TABLES, AND PANELS
    ==================================================
    
    Data containers should feel like organized living systems.
    
    Use:
    
    * greenhouse-panel cards
    * solar-grid table headers
    * leaf-vein separators
    * breathable row spacing
    * root-network grouping lines
    * warm hover states
    * status badges that feel like ecological indicators
    
    Tables must remain tables.
    
    Cards must preserve their content and role.
    
    Panels should feel layered, organic, and intentionally crafted.
    
    ==================================================
    TEXTURE AND MATERIALITY
    ==================================================
    
    The interface should have a crafted material quality.
    
    Use subtle suggestions of:
    
    * recycled paper
    * plant fiber
    * ceramic
    * sunlit glass
    * bamboo-like structure
    * soft photovoltaic surfaces
    * bio-resin
    * terracotta
    * brushed natural metal
    
    Do not overdo texture.
    
    The result should remain clean, readable, and production-quality.
    
    ==================================================
    FINAL AESTHETIC TARGET
    ==================================================
    
    The final page should look like a hopeful ecological civilization built the interface.
    
    It should feel:
    
    * alive
    * breathable
    * cultivated
    * sun-powered
    * optimistic
    * bio-mechanical
    * civic
    * gentle
    * technically advanced
    * natural without being rustic
    
    The page must look substantially different from the original, but the application must behave exactly the same.
    
    
    Also tighten your main goal to this:
    
    text
    PRIMARY GOAL
    
    Transform the page into a dramatically reinterpreted bio-mechanical solarpunk interface.
    
    The result should look alive, utopian, ecological, and technologically advanced, while preserving the exact same functionality, DOM hooks, accessibility, responsiveness, and user flows.
    
    This is not a recolor. It is a visual reinterpretation using CSS, existing semantic structure, safe wrappers, and decorative non-functional elements only.
    
