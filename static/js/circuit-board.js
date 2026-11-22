/**
 * Electrodesk - Photorealistic 3D Exploded-Layer PCB Intro Scene
 * Modular Three.js Implementation
 * 
 * Visual Target: Layer Stack PCB floating over warm paper studio.
 * Layers:
 *  - Screws & Heatsink (Top floating)
 *  - Components (ICs, Ports, GPIO, Capacitors, SMD passives, drifting motes)
 *  - Frosted Translucent Top Film (with faint trace & silkscreen art)
 *  - Deep Green Solder-Mask PCB (with copper traces, vias, gold pads)
 *  - Copper/Tan FR-4 Substrate Layer (with copper pour & drill holes)
 *  - Four Standoff Pillars (linking the stack)
 *  - Soft contact shadow floor
 */

(function (global) {
    'use strict';

    // =========================================================================
    // 1. NAMED CONSTANTS & PALETTES
    // =========================================================================
    const COLORS = {
        SOLDER_MASK: 0x14532d,       // Deep emerald green glossy solder mask (#14532d)
        SUBSTRATE_TAN: 0xc27838,     // Warm copper/tan FR-4 substrate (#c27838)
        COPPER_TRACE: 0xd97706,      // Copper tracks & pour (#d97706)
        GOLD_ENIG: 0xf59e0b,         // Electroless Nickel Immersion Gold pads & pins (#f59e0b)
        ALUMINUM_HEATSINK: 0xd8dde4, // Anodized / brushed aluminum (#d8dde4)
        BRUSHED_STEEL: 0xcbd5e1,     // Metal connector shields (#cbd5e1)
        USB3_BLUE: 0x0284c7,         // Vivid USB 3.0 blue tongue (#0284c7)
        FROSTED_FILM: 0xf8fafc,      // Translucent frosted film layer
        CHIP_BODY: 0x15181c,         // Near-black IC epoxy molding compound (#15181c)
        STANDOFF_BLACK: 0x27272a,    // Black oxide / dark steel standoffs
        STANDOFF_BRASS: 0xd97706,    // Brass hex standoff option
        SCREW_STEEL: 0xe2e8f0,       // Polished steel Phillips screws
        LED_CYAN: 0x22d3ee,          // Cyan power LED
        LED_AMBER: 0xfbbf24,         // Amber activity LED
        SMD_CAPACITOR: 0xb45309,     // Caramel ceramic capacitor body
        SMD_RESISTOR: 0x18181b       // Black resistor body
    };

    const GAPS = {
        // Vertical Y offsets in EXPLODED state
        EXPLODED: {
            STANDOFF_FEET: -1.75,
            SUBSTRATE: -0.90,
            MAIN_PCB: 0.15,
            FROSTED_FILM: 1.15,
            SMD_PARTS: 1.80,
            COMPONENTS: 2.50,
            HEATSINK: 3.45,
            SCREWS: 4.30
        },
        // Vertical Y offsets in ASSEMBLED state
        ASSEMBLED: {
            STANDOFF_FEET: -0.16,
            SUBSTRATE: -0.04,
            MAIN_PCB: 0.02,
            FROSTED_FILM: 0.06,
            SMD_PARTS: 0.08,
            COMPONENTS: 0.10,
            HEATSINK: 0.22,
            SCREWS: 0.11
        }
    };

    const TIMINGS = {
        EXPLODED_HOLD: 4200,      // Time (ms) spent floating exploded in idle
        ASSEMBLE_DURATION: 1800,  // Smooth ease duration from exploded to assembled
        ASSEMBLED_HOLD: 3200,     // Time (ms) spent assembled / powered on
        EXPLODE_DURATION: 1800    // Smooth ease duration from assembled back to exploded
    };
    TIMINGS.CYCLE_TOTAL = TIMINGS.EXPLODED_HOLD + TIMINGS.ASSEMBLE_DURATION + TIMINGS.ASSEMBLED_HOLD + TIMINGS.EXPLODE_DURATION;

    // Board Dimensions
    const BOARD_WIDTH = 4.4;
    const BOARD_HEIGHT = 0.05;
    const BOARD_DEPTH = 3.0;
    const CORNER_HOLES = [
        { x: -1.95, z: -1.30 },
        { x:  1.95, z: -1.30 },
        { x: -1.95, z:  1.30 },
        { x:  1.95, z:  1.30 }
    ];

    // =========================================================================
    // 2. WEBGL CAPABILITY & FALLBACK
    // =========================================================================
    function isWebGLAvailable() {
        try {
            const canvas = document.createElement('canvas');
            return !!(window.WebGLRenderingContext && (
                canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
            ));
        } catch (e) {
            return false;
        }
    }

    function showFallback(container, statusText) {
        if (!container) return;
        const canvas = document.getElementById('login-board-canvas');
        if (canvas) canvas.style.display = 'none';

        const fallback = document.createElement('div');
        fallback.className = 'login-board-fallback';
        fallback.innerHTML = `
            <div class="fallback-glow"></div>
            <div class="fallback-chip-icon">
                <i class="bi bi-cpu-fill"></i>
            </div>
            <div class="fallback-caption">ELECTRODESK 3D HARDWARE VIEW</div>
        `;
        container.appendChild(fallback);
        if (statusText) statusText.textContent = '2D PREVIEW MODE // WEBGL OFFLINE';
    }

    // =========================================================================
    // 3. PROCEDURAL TEXTURE GENERATORS (100% Offline, Zero Assets)
    // =========================================================================

    /**
     * Rounded Box Geometry Generator using ExtrudeGeometry (Bevel ~0.02)
     */
    function createRoundedBox(w, h, d, bevel = 0.02) {
        const b = Math.min(bevel, w * 0.15, h * 0.15, d * 0.15);
        const shape = new THREE.Shape();
        const hw = w / 2 - b;
        const hh = h / 2 - b;
        shape.moveTo(-hw, hh);
        shape.lineTo(hw, hh);
        shape.lineTo(hw, -hh);
        shape.lineTo(-hw, -hh);
        shape.closePath();

        const geo = new THREE.ExtrudeGeometry(shape, {
            depth: d - b * 2,
            bevelEnabled: true,
            bevelSegments: 2,
            steps: 1,
            bevelSize: b,
            bevelThickness: b
        });
        geo.center();
        return geo;
    }

    /**
     * Procedural Main PCB Green Solder Mask Texture (Color Map + Bump Map)
     */
    function generatePcbTextures(renderer) {
        const cCanvas = document.createElement('canvas');
        cCanvas.width = 2048;
        cCanvas.height = 2048;
        const c = cCanvas.getContext('2d');

        const bCanvas = document.createElement('canvas');
        bCanvas.width = 2048;
        bCanvas.height = 2048;
        const b = bCanvas.getContext('2d');

        // Solder mask base: Deep Emerald Green (#14532d)
        c.fillStyle = '#14532d';
        c.fillRect(0, 0, 2048, 2048);

        b.fillStyle = '#111111';
        b.fillRect(0, 0, 2048, 2048);

        // Ground pour polygons (subtle darker green where copper pour is present)
        c.fillStyle = '#166534';
        c.fillRect(120, 120, 1808, 1808);
        b.fillStyle = '#2a2a2a';
        b.fillRect(120, 120, 1808, 1808);

        // Isolation moat around edge
        c.strokeStyle = '#0f3e21';
        c.lineWidth = 14;
        c.strokeRect(100, 100, 1848, 1848);

        // High-Speed Copper Circuit Traces (45-degree octagonal routing)
        c.strokeStyle = '#d97706'; // Warm copper tone under glossy clearcoat
        c.lineWidth = 7;
        c.lineCap = 'round';
        c.lineJoin = 'round';

        b.strokeStyle = '#888888'; // Raised trace bump relief
        b.lineWidth = 7;
        b.lineCap = 'round';
        b.lineJoin = 'round';

        const traces = [
            // CPU to DRAM buses
            [[1024, 1024], [1300, 1024], [1400, 840], [1680, 840]],
            [[1024, 980],  [1280, 980],  [1360, 800], [1680, 800]],
            [[1024, 1068], [1280, 1068], [1360, 1220], [1680, 1220]],
            [[1024, 1112], [1300, 1112], [1400, 1260], [1680, 1260]],
            // CPU to Ports (USB & Ethernet)
            [[960, 1024],  [640, 1024],  [520, 760],  [280, 760]],
            [[960, 980],   [620, 980],   [500, 720],  [280, 720]],
            [[960, 1068],  [620, 1068],  [500, 1340], [280, 1340]],
            [[960, 1112],  [640, 1112],  [520, 1380], [280, 1380]],
            // GPIO Header Bus
            [[1024, 920],  [1024, 600],  [1200, 420], [1580, 420]],
            [[980, 920],   [980, 580],   [1160, 380], [1580, 380]],
            [[1068, 920],  [1068, 620],  [1240, 460], [1580, 460]],
            // Power rails
            [[500, 400],   [700, 400],   [840, 700],  [840, 1024]],
            [[500, 1640],  [760, 1640],  [840, 1360], [840, 1024]]
        ];

        traces.forEach(pts => {
            c.beginPath();
            b.beginPath();
            c.moveTo(pts[0][0], pts[0][1]);
            b.moveTo(pts[0][0], pts[0][1]);
            for (let i = 1; i < pts.length; i++) {
                c.lineTo(pts[i][0], pts[i][1]);
                b.lineTo(pts[i][0], pts[i][1]);
            }
            c.stroke();
            b.stroke();
        });

        // Annular Ring Vias (Plated Through-Hole vias with gold rings & dark centers)
        function drawVia(x, y) {
            c.fillStyle = '#f59e0b'; // Gold ring
            c.beginPath(); c.arc(x, y, 10, 0, Math.PI * 2); c.fill();
            c.fillStyle = '#0f172a'; // Drill center
            c.beginPath(); c.arc(x, y, 4, 0, Math.PI * 2); c.fill();

            b.fillStyle = '#aaaaaa';
            b.beginPath(); b.arc(x, y, 10, 0, Math.PI * 2); b.fill();
            b.fillStyle = '#000000'; // Recessed hole
            b.beginPath(); b.arc(x, y, 4, 0, Math.PI * 2); b.fill();
        }

        // Scatter vias along ground stitch & bus lines
        for (let vx = 300; vx <= 1700; vx += 140) {
            drawVia(vx, 220);
            drawVia(vx, 1820);
        }
        for (let vy = 300; vy <= 1700; vy += 140) {
            drawVia(220, vy);
            drawVia(1820, vy);
        }
        // Via stitch clusters around CPU and DRAM
        [
            [920, 920], [920, 1120], [1120, 920], [1120, 1120],
            [1380, 780], [1380, 860], [1380, 1200], [1380, 1280]
        ].forEach(([vx, vy]) => drawVia(vx, vy));

        // Gold SMT Component Pads (ENIG Electroless Nickel Immersion Gold)
        c.fillStyle = '#f59e0b';
        b.fillStyle = '#bbbbbb';

        // CPU BGA pad grid
        for (let r = -6; r <= 6; r++) {
            for (let k = -6; k <= 6; k++) {
                if (Math.abs(r) > 1 || Math.abs(k) > 1) {
                    c.fillRect(1024 + r * 24 - 5, 1024 + k * 24 - 5, 10, 10);
                    b.fillRect(1024 + r * 24 - 5, 1024 + k * 24 - 5, 10, 10);
                }
            }
        }

        // DRAM SMT footprint pads
        [-340, 340].forEach(yOff => {
            for (let p = -5; p <= 5; p++) {
                c.fillRect(1520 - 70, 1024 + yOff + p * 20 - 4, 18, 9);
                c.fillRect(1520 + 70, 1024 + yOff + p * 20 - 4, 18, 9);
                b.fillRect(1520 - 70, 1024 + yOff + p * 20 - 4, 18, 9);
                b.fillRect(1520 + 70, 1024 + yOff + p * 20 - 4, 18, 9);
            }
        });

        // Crisp White Silkscreen Typography & Legend (Industrial Standard)
        c.fillStyle = '#f8fafc';
        c.font = 'bold 36px "Inter", monospace';
        c.fillText('ELECTRODESK SBC-V3.2', 240, 280);
        c.font = '22px "Inter", monospace';
        c.fillStyle = '#cbd5e1';
        c.fillText('MODEL 4B // 64-BIT OCTA-CORE', 240, 320);
        c.fillText('4-LAYER HIGH-TG FR-4 STACK', 240, 352);
        c.fillText('U1 SoC', 970, 850);
        c.fillText('U2 DRAM-A', 1460, 710);
        c.fillText('U3 DRAM-B', 1460, 1420);
        c.fillText('J1 USB 3.0', 210, 1550);
        c.fillText('J2 GbE LAN', 210, 620);
        c.fillText('GPIO 40-PIN', 1280, 270);
        c.fillText('▲ PIN 1', 1160, 270);

        // Fiducials & CE/RoHS Marks
        c.strokeStyle = '#f8fafc';
        c.lineWidth = 3;
        c.strokeRect(900, 900, 248, 248); // CPU Courtyard
        c.strokeRect(1400, 720, 240, 160); // DRAM Courtyard
        c.strokeRect(1400, 1160, 240, 160);

        // Corner Mount Pad Rings
        [
            [120, 120], [1928, 120], [120, 1928], [1928, 1928]
        ].forEach(([cx, cy]) => {
            c.strokeStyle = '#f59e0b';
            c.lineWidth = 12;
            c.beginPath(); c.arc(cx, cy, 64, 0, Math.PI * 2); c.stroke();
            b.strokeStyle = '#cccccc';
            b.lineWidth = 12;
            b.beginPath(); b.arc(cx, cy, 64, 0, Math.PI * 2); b.stroke();
        });

        const maxAniso = renderer ? renderer.capabilities.getMaxAnisotropy() : 4;

        const colorTex = new THREE.CanvasTexture(cCanvas);
        colorTex.generateMipmaps = true;
        colorTex.anisotropy = maxAniso;

        const bumpTex = new THREE.CanvasTexture(bCanvas);
        bumpTex.generateMipmaps = true;
        bumpTex.anisotropy = maxAniso;

        return { colorTex, bumpTex };
    }

    /**
     * Procedural Copper/Tan Substrate Layer Texture
     */
    function generateSubstrateTexture(renderer) {
        const canvas = document.createElement('canvas');
        canvas.width = 1024;
        canvas.height = 1024;
        const ctx = canvas.getContext('2d');

        // FR-4 laminate core: warm translucent copper/tan
        ctx.fillStyle = '#b45309';
        ctx.fillRect(0, 0, 1024, 1024);

        // Copper pour planes
        ctx.fillStyle = '#d97706';
        ctx.fillRect(60, 60, 904, 904);

        // Internal ground planes and routing clearance splits
        ctx.strokeStyle = '#92400e';
        ctx.lineWidth = 6;
        ctx.strokeRect(80, 80, 864, 864);

        // Thermal copper hatch pattern
        ctx.strokeStyle = 'rgba(245, 158, 11, 0.25)';
        ctx.lineWidth = 2;
        for (let i = 0; i < 1024; i += 24) {
            ctx.beginPath();
            ctx.moveTo(i, 0); ctx.lineTo(i, 1024); ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, i); ctx.lineTo(1024, i); ctx.stroke();
        }

        // Corner drill holes
        ctx.fillStyle = '#1e1b18';
        [
            [60, 60], [964, 60], [60, 964], [964, 964]
        ].forEach(([hx, hy]) => {
            ctx.beginPath();
            ctx.arc(hx, hy, 28, 0, Math.PI * 2);
            ctx.fill();
        });

        const maxAniso = renderer ? renderer.capabilities.getMaxAnisotropy() : 4;
        const tex = new THREE.CanvasTexture(canvas);
        tex.generateMipmaps = true;
        tex.anisotropy = maxAniso;
        return tex;
    }

    /**
     * Procedural Frosted Top Film Texture
     */
    function generateFrostedFilmTexture(renderer) {
        const canvas = document.createElement('canvas');
        canvas.width = 1024;
        canvas.height = 1024;
        const ctx = canvas.getContext('2d');

        // Translucent frosted base with fine trace art
        ctx.fillStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.fillRect(0, 0, 1024, 1024);

        // Faint white alignment grid lines & component stencil apertures
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
        ctx.lineWidth = 2;
        ctx.strokeRect(50, 50, 924, 924);

        // Component courtyard stencil apertures
        ctx.strokeRect(450, 450, 124, 124); // SoC
        ctx.strokeRect(680, 360, 120, 80);  // DRAM A
        ctx.strokeRect(680, 580, 120, 80);  // DRAM B
        ctx.strokeRect(100, 300, 100, 160); // Ports

        // Faint trace guides
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.20)';
        ctx.beginPath();
        ctx.moveTo(512, 450); ctx.lineTo(512, 200); ctx.lineTo(750, 200);
        ctx.moveTo(512, 574); ctx.lineTo(512, 824); ctx.lineTo(750, 824);
        ctx.moveTo(450, 512); ctx.lineTo(250, 512);
        ctx.stroke();

        // Registration fiducials
        ctx.fillStyle = 'rgba(255, 255, 255, 0.45)';
        [
            [100, 100], [924, 100], [100, 924], [924, 924]
        ].forEach(([fx, fy]) => {
            ctx.beginPath();
            ctx.arc(fx, fy, 8, 0, Math.PI * 2);
            ctx.fill();
        });

        const maxAniso = renderer ? renderer.capabilities.getMaxAnisotropy() : 4;
        const tex = new THREE.CanvasTexture(canvas);
        tex.generateMipmaps = true;
        tex.anisotropy = maxAniso;
        return tex;
    }

    /**
     * Procedural Laser-Engraved Chip Markings
     */
    function generateChipTexture(line1, line2, line3, renderer) {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 512;
        const ctx = canvas.getContext('2d');

        // Matte black epoxy body (#15181c)
        ctx.fillStyle = '#15181c';
        ctx.fillRect(0, 0, 512, 512);

        // Laser-etched typography
        ctx.fillStyle = '#94a3b8';
        ctx.font = 'bold 36px monospace';
        ctx.fillText(line1, 50, 170);

        ctx.font = '22px monospace';
        ctx.fillStyle = '#64748b';
        ctx.fillText(line2, 50, 230);
        ctx.fillText(line3, 50, 270);

        // Laser pin 1 dot
        ctx.fillStyle = '#475569';
        ctx.beginPath();
        ctx.arc(55, 55, 14, 0, Math.PI * 2);
        ctx.fill();

        // 2D DataMatrix code in corner
        ctx.fillStyle = '#94a3b8';
        for (let r = 0; r < 7; r++) {
            for (let k = 0; k < 7; k++) {
                if ((r + k) % 2 === 0 || (r === 0 && k === 6) || (r === 6 && k === 0)) {
                    ctx.fillRect(350 + k * 14, 50 + r * 14, 10, 10);
                }
            }
        }

        const maxAniso = renderer ? renderer.capabilities.getMaxAnisotropy() : 4;
        const tex = new THREE.CanvasTexture(canvas);
        tex.generateMipmaps = true;
        tex.anisotropy = maxAniso;
        return tex;
    }

    // =========================================================================
    // 4. MAIN SCENE INITIALIZER
    // =========================================================================
    function initCircuitBoardScene() {
        if (window.__circuitBoardInitialized) return;

        if (typeof THREE === 'undefined') {
            setTimeout(initCircuitBoardScene, 60);
            return;
        }

        const canvas = document.getElementById('login-board-canvas');
        const container = document.getElementById('login-canvas-container');
        const statusText = document.getElementById('scene-status-text');

        if (!canvas || !container) {
            setTimeout(initCircuitBoardScene, 60);
            return;
        }

        if (!isWebGLAvailable()) {
            showFallback(container, statusText);
            return;
        }

        window.__circuitBoardInitialized = true;

        const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        // Container Dimensions
        let width = Math.max(container.clientWidth || 0, 360);
        let height = Math.max(container.clientHeight || 0, 340);

        // ---------------------------------------------------------------------
        // 4.1 Three.js Scene, Camera & WebGLRenderer
        // ---------------------------------------------------------------------
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 100);
        camera.position.set(5.5, 4.6, 5.8);
        camera.lookAt(0, 0.35, 0);

        let renderer;
        try {
            renderer = new THREE.WebGLRenderer({
                canvas: canvas,
                alpha: true,
                antialias: true,
                powerPreference: 'high-performance'
            });
        } catch (err) {
            console.warn('WebGL init failed:', err);
            showFallback(container, statusText);
            return;
        }

        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setClearColor(0x000000, 0); // Transparent canvas; blends with page background
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 0.95;
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;

        // ---------------------------------------------------------------------
        // 4.2 Procedural Studio Environment for PBR Specular Reflections
        // ---------------------------------------------------------------------
        try {
            const pmrem = new THREE.PMREMGenerator(renderer);
            pmrem.compileEquirectangularShader();
            const envScene = new THREE.Scene();

            // Studio room shell
            const envRoom = new THREE.Mesh(
                new THREE.BoxGeometry(20, 20, 20),
                new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.85, side: THREE.BackSide })
            );
            envScene.add(envRoom);

            // Overhead softbox light panel
            const envTop = new THREE.Mesh(
                new THREE.PlaneGeometry(12, 12),
                new THREE.MeshBasicMaterial({ color: 0xffffff })
            );
            envTop.position.set(0, 9.8, 0);
            envTop.rotation.x = Math.PI / 2;
            envScene.add(envTop);

            // Key warm softbox panel (studio reflection)
            const envKey = new THREE.Mesh(
                new THREE.PlaneGeometry(8, 8),
                new THREE.MeshBasicMaterial({ color: 0xfff7ed })
            );
            envKey.position.set(7, 6, 7);
            envKey.lookAt(0, 0, 0);
            envScene.add(envKey);

            // Cyan rim softbox panel
            const envCyan = new THREE.Mesh(
                new THREE.PlaneGeometry(7, 7),
                new THREE.MeshBasicMaterial({ color: 0x38bdf8 })
            );
            envCyan.position.set(-7, 4, -6);
            envCyan.lookAt(0, 0, 0);
            envScene.add(envCyan);

            const envTexture = pmrem.fromScene(envScene, 0.04).texture;
            scene.environment = envTexture;
            pmrem.dispose();
        } catch (e) {
            console.warn('RoomEnvironment PMREM generation bypassed:', e);
        }

        // ---------------------------------------------------------------------
        // 4.3 Studio Floor with Soft Shadow & Ambient Warm Grounding
        // ---------------------------------------------------------------------
        const shadowFloor = new THREE.Mesh(
            new THREE.PlaneGeometry(16, 14),
            new THREE.ShadowMaterial({ opacity: 0.45 })
        );
        shadowFloor.rotation.x = -Math.PI / 2;
        shadowFloor.position.y = -0.42;
        shadowFloor.receiveShadow = true;
        scene.add(shadowFloor);

        // Procedural warm ground ambient vignette disc
        const glowCanvas = document.createElement('canvas');
        glowCanvas.width = 512;
        glowCanvas.height = 512;
        const gctx = glowCanvas.getContext('2d');
        const gGrad = gctx.createRadialGradient(256, 256, 20, 256, 256, 250);
        gGrad.addColorStop(0, 'rgba(217, 180, 130, 0.28)'); // warm paper highlight
        gGrad.addColorStop(0.35, 'rgba(34, 211, 238, 0.14)'); // subtle cyan rim glow
        gGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        gctx.fillStyle = gGrad;
        gctx.fillRect(0, 0, 512, 512);

        const floorGlowTex = new THREE.CanvasTexture(glowCanvas);
        const floorGlowMesh = new THREE.Mesh(
            new THREE.PlaneGeometry(8, 8),
            new THREE.MeshBasicMaterial({
                map: floorGlowTex,
                transparent: true,
                opacity: 0.35,
                blending: THREE.AdditiveBlending,
                depthWrite: false
            })
        );
        floorGlowMesh.rotation.x = -Math.PI / 2;
        floorGlowMesh.position.y = -0.415;
        scene.add(floorGlowMesh);

        // ---------------------------------------------------------------------
        // 4.4 Studio Natural Lighting Rig
        // ---------------------------------------------------------------------
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.45);
        scene.add(ambientLight);

        // Directional Key Light with PCF Soft Shadows
        const keyLight = new THREE.DirectionalLight(0xfffaed, 2.1);
        keyLight.position.set(6.2, 9.5, 5.8);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.width = 2048;
        keyLight.shadow.mapSize.height = 2048;
        keyLight.shadow.camera.near = 0.5;
        keyLight.shadow.camera.far = 28;
        keyLight.shadow.camera.left = -4.5;
        keyLight.shadow.camera.right = 4.5;
        keyLight.shadow.camera.top = 4.5;
        keyLight.shadow.camera.bottom = -4.5;
        keyLight.shadow.bias = -0.0003;
        keyLight.shadow.radius = 2.4;
        scene.add(keyLight);

        // Teal / Cyan Rim Light for Specular Edge Definition
        const rimLight = new THREE.DirectionalLight(0x22d3ee, 2.4);
        rimLight.position.set(-6.2, 4.0, -4.8);
        scene.add(rimLight);

        // Warm Fill Light from underneath
        const fillLight = new THREE.DirectionalLight(0xb45309, 0.25);
        fillLight.position.set(0, -4, 2);
        scene.add(fillLight);

        // ---------------------------------------------------------------------
        // 4.5 Materials Library
        // ---------------------------------------------------------------------
        const { colorTex: pcbColorTex, bumpTex: pcbBumpTex } = generatePcbTextures(renderer);
        const substrateTex = generateSubstrateTexture(renderer);
        const frostedFilmTex = generateFrostedFilmTexture(renderer);
        const cpuTex = generateChipTexture('ELECTRODESK', 'EDK-9900PRO // OCTA', '64-BIT // 2.8GHz ARM', renderer);
        const ramTex = generateChipTexture('ELECTRODESK', 'LPDDR5X 16GB', '8533Mbps DUAL-CH', renderer);

        const materials = {
            // Layer 1: Substrate
            substrate: new THREE.MeshStandardMaterial({
                map: substrateTex,
                color: COLORS.SUBSTRATE_TAN,
                metalness: 0.55,
                roughness: 0.40,
                bumpMap: substrateTex,
                bumpScale: 0.006
            }),
            // Layer 2: Main Solder-Mask Green PCB (MeshPhysicalMaterial with Clearcoat)
            pcbGreen: new THREE.MeshPhysicalMaterial({
                color: COLORS.SOLDER_MASK,
                map: pcbColorTex,
                bumpMap: pcbBumpTex,
                bumpScale: 0.005,
                roughness: 0.35,
                metalness: 0.05,
                clearcoat: 0.85,
                clearcoatRoughness: 0.12
            }),
            // Layer 3: Translucent Frosted Top Film
            frostedFilm: new THREE.MeshPhysicalMaterial({
                map: frostedFilmTex,
                color: COLORS.FROSTED_FILM,
                transparent: true,
                opacity: 0.35,
                roughness: 0.20,
                metalness: 0.10,
                clearcoat: 0.60,
                clearcoatRoughness: 0.15
            }),
            // Gold ENIG Pins & Pads
            gold: new THREE.MeshStandardMaterial({
                color: COLORS.GOLD_ENIG,
                metalness: 1.0,
                roughness: 0.22
            }),
            // Brushed Aluminum Heatsink
            heatsinkAluminum: new THREE.MeshStandardMaterial({
                color: COLORS.ALUMINUM_HEATSINK,
                metalness: 0.95,
                roughness: 0.22
            }),
            // Brushed Steel Connector Housings
            brushedSteel: new THREE.MeshStandardMaterial({
                color: COLORS.BRUSHED_STEEL,
                metalness: 1.0,
                roughness: 0.32,
                envMapIntensity: 1.2
            }),
            // Port Cavities Dark Interior
            portInteriorDark: new THREE.MeshStandardMaterial({
                color: 0x090d16,
                roughness: 0.85,
                metalness: 0.10
            }),
            // USB 3.0 Tongue Blue Plastic
            usb3Blue: new THREE.MeshStandardMaterial({
                color: COLORS.USB3_BLUE,
                roughness: 0.35,
                metalness: 0.05
            }),
            // Laser-Etched ICs
            chipCpu: new THREE.MeshStandardMaterial({
                color: COLORS.CHIP_BODY,
                map: cpuTex,
                metalness: 0.08,
                roughness: 0.70
            }),
            chipRam: new THREE.MeshStandardMaterial({
                color: COLORS.CHIP_BODY,
                map: ramTex,
                metalness: 0.08,
                roughness: 0.70
            }),
            chipMatte: new THREE.MeshStandardMaterial({
                color: COLORS.CHIP_BODY,
                metalness: 0.08,
                roughness: 0.75
            }),
            // Header Plastic Body
            headerPlastic: new THREE.MeshStandardMaterial({
                color: 0x18181b,
                roughness: 0.85
            }),
            // SMD Passives
            smdCapacitor: new THREE.MeshStandardMaterial({
                color: COLORS.SMD_CAPACITOR,
                metalness: 0.60,
                roughness: 0.30
            }),
            smdResistor: new THREE.MeshStandardMaterial({
                color: COLORS.SMD_RESISTOR,
                metalness: 0.20,
                roughness: 0.60
            }),
            // Corner Standoff Pillars & Screws
            standoffPillar: new THREE.MeshStandardMaterial({
                color: COLORS.STANDOFF_BLACK,
                metalness: 0.85,
                roughness: 0.28
            }),
            screwSteel: new THREE.MeshStandardMaterial({
                color: COLORS.SCREW_STEEL,
                metalness: 0.95,
                roughness: 0.18
            }),
            // Indicator LEDs
            ledCyan: new THREE.MeshStandardMaterial({
                color: COLORS.LED_CYAN,
                emissive: COLORS.LED_CYAN,
                emissiveIntensity: 0.85,
                roughness: 0.20
            }),
            ledAmber: new THREE.MeshStandardMaterial({
                color: COLORS.LED_AMBER,
                emissive: 0xd97706,
                emissiveIntensity: 0.60,
                roughness: 0.20
            }),
            // Atmospheric Drifting Dust / Particles
            particleMat: new THREE.MeshBasicMaterial({
                color: 0x7dd3fc,
                transparent: true,
                opacity: 0.65,
                blending: THREE.AdditiveBlending
            })
        };

        // ---------------------------------------------------------------------
        // 4.6 Exploded Layer Stack Hierarchy
        // ---------------------------------------------------------------------
        const boardRoot = new THREE.Group();
        boardRoot.scale.set(1.22, 1.22, 1.22);
        boardRoot.rotation.x = 0.22;
        boardRoot.rotation.y = -0.48;
        scene.add(boardRoot);

        const animatedLayers = [];

        function registerLayer(group, explodedY, assembledY, options = {}) {
            group.position.y = prefersReducedMotion ? assembledY : explodedY;
            boardRoot.add(group);
            animatedLayers.push({
                group: group,
                explodedY: explodedY,
                assembledY: assembledY,
                rotatesY: !!options.rotatesY,
                initialRotY: group.rotation.y,
                turns: options.turns || 0
            });
            return group;
        }

        // =====================================================================
        // LAYER 1: Four Standoff Pillars linking the stack
        // =====================================================================
        const standoffsGroup = new THREE.Group();
        CORNER_HOLES.forEach(pos => {
            const pillar = new THREE.Mesh(
                new THREE.CylinderGeometry(0.13, 0.13, 0.36, 16),
                materials.standoffPillar
            );
            pillar.position.set(pos.x, 0, pos.z);
            pillar.castShadow = true;
            pillar.receiveShadow = true;
            standoffsGroup.add(pillar);
        });
        registerLayer(standoffsGroup, GAPS.EXPLODED.STANDOFF_FEET, GAPS.ASSEMBLED.STANDOFF_FEET);

        // =====================================================================
        // LAYER 2: Copper/Tan Substrate Layer (FR-4 core with copper pour)
        // =====================================================================
        const substrateGroup = new THREE.Group();
        const substrateMesh = new THREE.Mesh(
            createRoundedBox(BOARD_WIDTH, 0.04, BOARD_DEPTH, 0.02),
            materials.substrate
        );
        substrateMesh.castShadow = true;
        substrateMesh.receiveShadow = true;
        substrateGroup.add(substrateMesh);

        // Copper ground pads at corners
        CORNER_HOLES.forEach(pos => {
            const pad = new THREE.Mesh(
                new THREE.CylinderGeometry(0.20, 0.20, 0.045, 16),
                materials.gold
            );
            pad.position.set(pos.x, 0, pos.z);
            substrateGroup.add(pad);
        });
        registerLayer(substrateGroup, GAPS.EXPLODED.SUBSTRATE, GAPS.ASSEMBLED.SUBSTRATE);

        // =====================================================================
        // LAYER 3: Main Green Solder-Mask PCB with copper traces & gold pads
        // =====================================================================
        const pcbGroup = new THREE.Group();
        const pcbMesh = new THREE.Mesh(
            createRoundedBox(BOARD_WIDTH, 0.06, BOARD_DEPTH, 0.02),
            materials.pcbGreen
        );
        pcbMesh.castShadow = true;
        pcbMesh.receiveShadow = true;
        pcbGroup.add(pcbMesh);
        registerLayer(pcbGroup, GAPS.EXPLODED.MAIN_PCB, GAPS.ASSEMBLED.MAIN_PCB);

        // =====================================================================
        // LAYER 4: Translucent Frosted Top Film with faint trace art
        // =====================================================================
        const filmGroup = new THREE.Group();
        const filmMesh = new THREE.Mesh(
            createRoundedBox(BOARD_WIDTH, 0.025, BOARD_DEPTH, 0.02),
            materials.frostedFilm
        );
        filmGroup.add(filmMesh);
        registerLayer(filmGroup, GAPS.EXPLODED.FROSTED_FILM, GAPS.ASSEMBLED.FROSTED_FILM);

        // =====================================================================
        // LAYER 5: 60+ Tiny SMD Resistors & Capacitors (InstancedMesh)
        // =====================================================================
        const smdCount = 72;
        const smdGeo = createRoundedBox(0.12, 0.05, 0.07, 0.01);
        const smdInstanced = new THREE.InstancedMesh(smdGeo, materials.smdCapacitor, smdCount);
        smdInstanced.castShadow = true;
        smdInstanced.receiveShadow = true;

        const dummy = new THREE.Object3D();
        let smdIdx = 0;

        // Decoupling ring surrounding CPU
        for (let x = -0.72; x <= 0.72; x += 0.24) {
            dummy.position.set(x, 0.03, -0.70);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(smdIdx++, dummy.matrix);

            dummy.position.set(x, 0.03, 0.70);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(smdIdx++, dummy.matrix);
        }

        // DRAM filter banks
        for (let z = -0.8; z <= 0.8; z += 0.20) {
            dummy.position.set(1.28, 0.03, z);
            dummy.rotation.y = Math.PI / 2;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(smdIdx++, dummy.matrix);
        }

        // Voltage regulator and USB decoupling rails
        for (let z = -0.35; z <= 0.65; z += 0.16) {
            dummy.position.set(-1.15, 0.03, z);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(smdIdx++, dummy.matrix);

            dummy.position.set(-0.95, 0.03, z);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(smdIdx++, dummy.matrix);
        }

        // Remaining capacitors on peripheral tracks
        while (smdIdx < smdCount) {
            dummy.position.set(-0.5 + (smdIdx % 6) * 0.20, 0.03, -0.95);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(smdIdx++, dummy.matrix);
        }
        smdInstanced.instanceMatrix.needsUpdate = true;

        const smdGroup = new THREE.Group();
        smdGroup.add(smdInstanced);
        registerLayer(smdGroup, GAPS.EXPLODED.SMD_PARTS, GAPS.ASSEMBLED.SMD_PARTS);

        // =====================================================================
        // LAYER 6: Floating Components (ICs, Ports, GPIO Header, Capacitors)
        // =====================================================================
        const compGroup = new THREE.Group();

        // Central 64-bit SoC
        const cpuPkg = new THREE.Mesh(
            createRoundedBox(1.04, 0.09, 1.04, 0.02),
            materials.chipCpu
        );
        cpuPkg.castShadow = true;
        cpuPkg.receiveShadow = true;
        compGroup.add(cpuPkg);

        // SoC Heartbeat micro-LED
        const cpuLed = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.03, 0.06), materials.ledCyan);
        cpuLed.position.set(0.36, 0.05, 0.36);
        compGroup.add(cpuLed);

        // Dual LPDDR5X DRAM ICs
        [-0.44, 0.44].forEach(z => {
            const ram = new THREE.Mesh(
                createRoundedBox(0.56, 0.07, 0.76, 0.02),
                materials.chipRam
            );
            ram.position.set(0.90, 0, z);
            ram.castShadow = true;
            compGroup.add(ram);
        });

        // Stacked Dual USB-A 3.0 Housing (Brushed Steel with Blue Tongues)
        const usbBlock = new THREE.Mesh(
            createRoundedBox(0.72, 0.58, 0.82, 0.02),
            materials.brushedSteel
        );
        usbBlock.castShadow = true;
        usbBlock.receiveShadow = true;

        [-0.14, 0.14].forEach(yOff => {
            const cavity = new THREE.Mesh(
                new THREE.BoxGeometry(0.26, 0.18, 0.56),
                materials.portInteriorDark
            );
            cavity.position.set(-0.25, yOff, 0);
            usbBlock.add(cavity);

            // Blue USB3.0 Tongue
            const tongue = new THREE.Mesh(
                new THREE.BoxGeometry(0.20, 0.04, 0.44),
                materials.usb3Blue
            );
            tongue.position.set(-0.27, yOff - 0.045, 0);
            usbBlock.add(tongue);

            // Gold spring contact fingers
            for (let p = 0; p < 4; p++) {
                const pin = new THREE.Mesh(
                    new THREE.BoxGeometry(0.12, 0.012, 0.045),
                    materials.gold
                );
                pin.position.set(-0.27, yOff - 0.02, -0.15 + p * 0.10);
                usbBlock.add(pin);
            }
        });
        usbBlock.position.set(-1.68, 0.22, 0.88);
        compGroup.add(usbBlock);

        // RJ-45 Gigabit Ethernet Jack (Brushed Steel Housing with Cavity & LEDs)
        const ethBlock = new THREE.Mesh(
            createRoundedBox(0.78, 0.62, 0.86, 0.02),
            materials.brushedSteel
        );
        ethBlock.castShadow = true;
        ethBlock.receiveShadow = true;

        const ethCavity = new THREE.Mesh(
            new THREE.BoxGeometry(0.30, 0.44, 0.66),
            materials.portInteriorDark
        );
        ethCavity.position.set(-0.26, -0.04, 0);
        ethBlock.add(ethCavity);

        // 8 gold contact wire springs inside
        for (let i = 0; i < 8; i++) {
            const wire = new THREE.Mesh(
                new THREE.CylinderGeometry(0.008, 0.008, 0.14, 8),
                materials.gold
            );
            wire.rotation.z = Math.PI / 4;
            wire.position.set(-0.28, 0.10, -0.22 + i * 0.06);
            ethBlock.add(wire);
        }

        // Ethernet Status LEDs
        const ethLed1 = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.05), materials.ledCyan);
        ethLed1.position.set(-0.38, 0.25, -0.25);
        ethBlock.add(ethLed1);
        const ethLed2 = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.05), materials.ledAmber);
        ethLed2.position.set(-0.38, 0.25, 0.25);
        ethBlock.add(ethLed2);

        ethBlock.position.set(-1.68, 0.24, -0.55);
        compGroup.add(ethBlock);

        // 2x20 (40-Pin) Gold GPIO Header Strip via InstancedMesh
        const gpioBase = new THREE.Mesh(
            createRoundedBox(1.72, 0.12, 0.26, 0.01),
            materials.headerPlastic
        );
        gpioBase.position.set(0.68, 0.06, 1.20);
        gpioBase.castShadow = true;
        compGroup.add(gpioBase);

        const pinCount = 40;
        const pinGeo = new THREE.CylinderGeometry(0.022, 0.022, 0.38, 12);
        const pinInstanced = new THREE.InstancedMesh(pinGeo, materials.gold, pinCount);
        pinInstanced.castShadow = true;

        let pinIdx = 0;
        for (let col = -0.74; col <= 0.74; col += 0.185) {
            [-0.06, 0.06].forEach(rowZ => {
                dummy.position.set(0.68 + col, 0.25, 1.20 + rowZ);
                dummy.rotation.set(0, 0, 0);
                dummy.updateMatrix();
                pinInstanced.setMatrixAt(pinIdx++, dummy.matrix);
            });
        }
        pinInstanced.instanceMatrix.needsUpdate = true;
        compGroup.add(pinInstanced);

        // Cylindrical Electrolytic Filter Capacitors (Aluminum Can with Vents)
        [-0.85, -0.55].forEach((zPos, i) => {
            const capGroup = new THREE.Group();
            const can = new THREE.Mesh(
                new THREE.CylinderGeometry(0.18, 0.18, 0.42, 20),
                materials.chipMatte
            );
            can.castShadow = true;
            capGroup.add(can);

            // Aluminum stamped top vent groove
            const topDisc = new THREE.Mesh(
                new THREE.CylinderGeometry(0.178, 0.178, 0.02, 20),
                materials.heatsinkAluminum
            );
            topDisc.position.y = 0.21;
            capGroup.add(topDisc);

            capGroup.position.set(-0.25 + i * 0.22, 0.21, zPos);
            compGroup.add(capGroup);
        });

        registerLayer(compGroup, GAPS.EXPLODED.COMPONENTS, GAPS.ASSEMBLED.COMPONENTS);

        // =====================================================================
        // LAYER 7: Extruded Finned Aluminum Heatsink
        // =====================================================================
        const heatsinkGroup = new THREE.Group();
        const hsBase = new THREE.Mesh(
            createRoundedBox(1.10, 0.06, 1.10, 0.015),
            materials.heatsinkAluminum
        );
        hsBase.castShadow = true;
        hsBase.receiveShadow = true;
        heatsinkGroup.add(hsBase);

        const finCount = 14;
        const finSpacing = 0.98 / (finCount - 1);
        for (let i = 0; i < finCount; i++) {
            const fx = -0.49 + i * finSpacing;
            const fin = new THREE.Mesh(
                new THREE.BoxGeometry(0.022, 0.40, 1.06),
                materials.heatsinkAluminum
            );
            fin.position.set(fx, 0.23, 0);
            fin.castShadow = true;
            fin.receiveShadow = true;
            heatsinkGroup.add(fin);
        }
        heatsinkGroup.position.set(0, 0, 0);
        registerLayer(heatsinkGroup, GAPS.EXPLODED.HEATSINK, GAPS.ASSEMBLED.HEATSINK);

        // =====================================================================
        // LAYER 8: 4 Corner Screws (Tightening with spin rotation)
        // =====================================================================
        CORNER_HOLES.forEach(pos => {
            const screwGroup = new THREE.Group();
            const head = new THREE.Mesh(
                new THREE.CylinderGeometry(0.14, 0.13, 0.07, 16),
                materials.screwSteel
            );
            head.position.y = 0.035;
            head.castShadow = true;
            screwGroup.add(head);

            // Phillips cross slots
            const slot1 = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.02, 0.04), materials.chipMatte);
            slot1.position.y = 0.075;
            screwGroup.add(slot1);
            const slot2 = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.02, 0.18), materials.chipMatte);
            slot2.position.y = 0.075;
            screwGroup.add(slot2);

            const shank = new THREE.Mesh(
                new THREE.CylinderGeometry(0.05, 0.05, 0.30, 8),
                materials.screwSteel
            );
            shank.position.y = -0.13;
            shank.castShadow = true;
            screwGroup.add(shank);

            screwGroup.position.set(pos.x, 0, pos.z);
            registerLayer(screwGroup, GAPS.EXPLODED.SCREWS, GAPS.ASSEMBLED.SCREWS, {
                rotatesY: true,
                turns: 6.0
            });
        });

        // =====================================================================
        // LAYER 9: Drifting Atmospheric SMD Dust / Motes (InstancedMesh)
        // =====================================================================
        const particleCount = 42;
        const particleGeo = new THREE.BoxGeometry(0.035, 0.035, 0.035);
        const particleInstanced = new THREE.InstancedMesh(particleGeo, materials.particleMat, particleCount);

        const particleData = [];
        for (let i = 0; i < particleCount; i++) {
            const p = {
                x: (Math.random() - 0.5) * 4.6,
                y: 0.4 + Math.random() * 3.8,
                z: (Math.random() - 0.5) * 3.4,
                speedY: 0.15 + Math.random() * 0.25,
                rotSpeed: (Math.random() - 0.5) * 2.0,
                phase: Math.random() * Math.PI * 2
            };
            particleData.push(p);
            dummy.position.set(p.x, p.y, p.z);
            dummy.updateMatrix();
            particleInstanced.setMatrixAt(i, dummy.matrix);
        }
        particleInstanced.instanceMatrix.needsUpdate = true;
        boardRoot.add(particleInstanced);

        // ---------------------------------------------------------------------
        // 4.7 Animation & State Controller
        // ---------------------------------------------------------------------
        const startTime = performance.now();
        let isRunning = true;
        let isPoweringOn = false;
        let manualAssembleOverride = null; // null = auto loop; true/false = user hover/click toggle

        // Smooth cubic-bezier easing
        function easeInOutCubic(t) {
            return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
        }

        // Parallax cursor tracking
        const mouseTarget = { x: 0, y: 0 };
        const mouseCurrent = { x: 0, y: 0 };

        function onMouseMove(e) {
            const nx = (e.clientX / window.innerWidth) - 0.5;
            const ny = (e.clientY / window.innerHeight) - 0.5;
            mouseTarget.x = nx * 0.35;
            mouseTarget.y = ny * 0.25;
        }
        window.addEventListener('mousemove', onMouseMove, { passive: true });

        // Click / Hover interaction to snap or explode on demand
        function toggleAssemblyState() {
            if (manualAssembleOverride === null) {
                manualAssembleOverride = true;
            } else {
                manualAssembleOverride = !manualAssembleOverride;
            }
        }
        canvas.addEventListener('click', toggleAssemblyState);

        // Window resize handler
        function onWindowResize() {
            if (!container || !renderer || !camera) return;
            const newW = Math.max(container.clientWidth || 0, 360);
            const newH = Math.max(container.clientHeight || 0, 340);
            if (newW !== width || newH !== height) {
                width = newW;
                height = newH;
                camera.aspect = width / height;
                camera.updateProjectionMatrix();
                renderer.setSize(width, height);
            }
        }
        window.addEventListener('resize', onWindowResize);

        // Pause rendering when tab is hidden (saves 100% GPU / CPU)
        document.addEventListener('visibilitychange', () => {
            isRunning = !document.hidden;
            if (isRunning) requestAnimationFrame(renderLoop);
        });

        // ---------------------------------------------------------------------
        // 4.8 Main Render Loop
        // ---------------------------------------------------------------------
        let currentAssembleFactor = 0; // 0 = fully exploded, 1 = fully assembled

        function renderLoop(now) {
            if (!isRunning) return;

            // Responsive bounds check
            if (container && container.clientWidth > 0 && container.clientHeight > 0) {
                if (Math.abs(container.clientWidth - width) > 8 || Math.abs(container.clientHeight - height) > 8) {
                    onWindowResize();
                }
            }

            const elapsed = now - startTime;

            // Determine target assembly factor (0..1)
            let targetFactor = 0;

            if (prefersReducedMotion) {
                targetFactor = 1.0;
            } else if (manualAssembleOverride !== null) {
                targetFactor = manualAssembleOverride ? 1.0 : 0.0;
            } else {
                // Autonomous Cycle: Exploded Hold -> Assemble -> Assembled Hold -> Explode
                const cycleTime = elapsed % TIMINGS.CYCLE_TOTAL;

                if (cycleTime < TIMINGS.EXPLODED_HOLD) {
                    targetFactor = 0.0;
                    if (statusText && !isPoweringOn) {
                        statusText.textContent = 'EXPLODED LAYER STACK // STANDBY';
                    }
                } else if (cycleTime < TIMINGS.EXPLODED_HOLD + TIMINGS.ASSEMBLE_DURATION) {
                    const t = (cycleTime - TIMINGS.EXPLODED_HOLD) / TIMINGS.ASSEMBLE_DURATION;
                    targetFactor = easeInOutCubic(t);
                    if (statusText && !isPoweringOn) {
                        statusText.textContent = 'ASSEMBLING CIRCUIT BOARD...';
                    }
                } else if (cycleTime < TIMINGS.EXPLODED_HOLD + TIMINGS.ASSEMBLE_DURATION + TIMINGS.ASSEMBLED_HOLD) {
                    targetFactor = 1.0;
                    if (statusText && !isPoweringOn) {
                        statusText.textContent = 'ELECTRODESK HARDWARE ONLINE // ALL SYSTEMS NOMINAL';
                    }
                } else {
                    const t = 1.0 - (cycleTime - (TIMINGS.EXPLODED_HOLD + TIMINGS.ASSEMBLE_DURATION + TIMINGS.ASSEMBLED_HOLD)) / TIMINGS.EXPLODE_DURATION;
                    targetFactor = easeInOutCubic(t);
                    if (statusText && !isPoweringOn) {
                        statusText.textContent = 'EXPLODING LAYERS...';
                    }
                }
            }

            // Smooth interpolation of current assembly factor
            const lerpSpeed = prefersReducedMotion ? 1.0 : 0.08;
            currentAssembleFactor += (targetFactor - currentAssembleFactor) * lerpSpeed;

            // Apply positions and spin to each exploded layer
            animatedLayers.forEach(layer => {
                layer.group.position.y = THREE.MathUtils.lerp(layer.explodedY, layer.assembledY, currentAssembleFactor);
                if (layer.rotatesY) {
                    layer.group.rotation.y = layer.initialRotY + (layer.turns * Math.PI * 2 * currentAssembleFactor);
                }
            });

            // Update drifting particles
            const timeSec = now * 0.001;
            for (let i = 0; i < particleCount; i++) {
                const p = particleData[i];
                const py = p.y + Math.sin(timeSec * p.speedY + p.phase) * 0.18;
                const px = p.x + Math.cos(timeSec * 0.2 + p.phase) * 0.08;
                dummy.position.set(px, py, p.z);
                dummy.rotation.set(timeSec * p.rotSpeed, timeSec * p.rotSpeed, 0);
                dummy.updateMatrix();
                particleInstanced.setMatrixAt(i, dummy.matrix);
            }
            particleInstanced.instanceMatrix.needsUpdate = true;

            // Idle float breathing & mouse parallax tilt
            const idleBreath = Math.sin(timeSec * 1.2) * 0.06;
            boardRoot.position.y = idleBreath;

            mouseCurrent.x += (mouseTarget.x - mouseCurrent.x) * 0.045;
            mouseCurrent.y += (mouseTarget.y - mouseCurrent.y) * 0.045;

            boardRoot.rotation.y = -0.48 + Math.sin(timeSec * 0.35) * 0.05 + mouseCurrent.x;
            boardRoot.rotation.x =  0.22 + Math.cos(timeSec * 0.40) * 0.03 + mouseCurrent.y;

            // LED pulse behavior
            if (currentAssembleFactor > 0.85 && !isPoweringOn) {
                materials.ledCyan.emissiveIntensity = 0.90 + Math.sin(timeSec * 4.0) * 0.40;
                materials.ledAmber.emissiveIntensity = 0.60 + Math.cos(timeSec * 3.0) * 0.30;
            } else if (!isPoweringOn) {
                materials.ledCyan.emissiveIntensity = 0.50;
                materials.ledAmber.emissiveIntensity = 0.30;
            }

            renderer.render(scene, camera);
            requestAnimationFrame(renderLoop);
        }

        requestAnimationFrame(renderLoop);

        // ---------------------------------------------------------------------
        // 4.9 Login Form Submit Power-On Sequence
        // ---------------------------------------------------------------------
        global.triggerBoardPowerOn = function (callback) {
            if (isPoweringOn) {
                if (callback) callback();
                return;
            }
            isPoweringOn = true;

            // Snap layers together immediately
            manualAssembleOverride = true;

            if (statusText) statusText.textContent = 'SYSTEM POWERING ON...';

            const overlay = document.getElementById('login-poweron-overlay');
            if (overlay) overlay.classList.add('login-poweron-active');

            materials.ledCyan.emissiveIntensity = 5.0;
            materials.ledCyan.emissive.setHex(0x38bdf8);

            camera.position.z -= 0.40;
            camera.position.y += 0.18;

            setTimeout(() => {
                if (callback) callback();
            }, 450);
        };

        // ---------------------------------------------------------------------
        // 4.10 Resource Disposal (Memory Leak Prevention)
        // ---------------------------------------------------------------------
        function disposeScene() {
            isRunning = false;
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('resize', onWindowResize);
            canvas.removeEventListener('click', toggleAssemblyState);

            scene.traverse(obj => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) {
                    if (Array.isArray(obj.material)) {
                        obj.material.forEach(m => m.dispose());
                    } else {
                        obj.material.dispose();
                    }
                }
            });

            if (pcbColorTex) pcbColorTex.dispose();
            if (pcbBumpTex) pcbBumpTex.dispose();
            if (substrateTex) substrateTex.dispose();
            if (frostedFilmTex) frostedFilmTex.dispose();
            if (cpuTex) cpuTex.dispose();
            if (ramTex) ramTex.dispose();
            if (floorGlowTex) floorGlowTex.dispose();

            if (renderer) {
                renderer.dispose();
                renderer.forceContextLoss();
            }
            window.__circuitBoardInitialized = false;
        }

        window.addEventListener('beforeunload', disposeScene, { once: true });
    }

    // Export module
    global.initCircuitBoardScene = initCircuitBoardScene;
    global.initLoginScene = initCircuitBoardScene;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCircuitBoardScene);
    } else {
        initCircuitBoardScene();
    }
    window.addEventListener('load', initCircuitBoardScene);

})(typeof window !== 'undefined' ? window : this);
