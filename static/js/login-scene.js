/**
 * Electrodesk - Photorealistic 3D Exploded Circuit Board Intro Scene
 * Built strictly with Three.js BoxGeometry, CylinderGeometry & ExtrudeGeometry (Bevels).
 * Scoped exclusively to the /login page.
 */

(function () {
    'use strict';

    let sceneInitialized = false;

    // WebGL Capability Check
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

    function initScene() {
        if (sceneInitialized) return;

        if (typeof THREE === 'undefined') {
            setTimeout(initScene, 60);
            return;
        }

        const canvas = document.getElementById('login-board-canvas');
        const container = document.getElementById('login-canvas-container');
        const statusText = document.getElementById('scene-status-text');

        if (!canvas || !container) {
            setTimeout(initScene, 60);
            return;
        }

        if (!isWebGLAvailable()) {
            console.warn('WebGL not supported. Displaying clean studio gradient.');
            if (statusText) statusText.textContent = 'GRAPHICS ACCELERATION OFFLINE';
            return;
        }

        sceneInitialized = true;

        const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        // Container Dimensions
        let width = Math.max(container.clientWidth || 0, 360);
        let height = Math.max(container.clientHeight || 0, 340);

        // 1. Scene, Camera, Renderer
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(36, width / height, 0.1, 100);
        camera.position.set(5.2, 4.4, 5.6);
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
            console.warn('WebGLRenderer init failed:', err);
            return;
        }

        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setClearColor(0x000000, 0); // 100% transparent canvas for studio gradient

        // Tone Mapping & Exposure: ACESFilmicToneMapping, exposure ~0.9
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 0.90;

        // Soft Shadows
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;

        // 2. Procedural RoomEnvironment for Photorealistic PBR Reflections
        try {
            const pmremGenerator = new THREE.PMREMGenerator(renderer);
            pmremGenerator.compileEquirectangularShader();

            const envScene = new THREE.Scene();

            // Studio room interior box with grayscale roughness
            const roomGeo = new THREE.BoxGeometry(24, 24, 24);
            const roomMat = new THREE.MeshStandardMaterial({
                color: 0x64748b,
                roughness: 0.85,
                metalness: 0.1,
                side: THREE.BackSide
            });
            const room = new THREE.Mesh(roomGeo, roomMat);
            envScene.add(room);

            // Overhead softbox
            const topSoftbox = new THREE.Mesh(
                new THREE.PlaneGeometry(12, 12),
                new THREE.MeshBasicMaterial({ color: 0xffffff })
            );
            topSoftbox.position.set(0, 11.9, 0);
            topSoftbox.rotation.x = Math.PI / 2;
            envScene.add(topSoftbox);

            // Key studio softbox
            const keySoftbox = new THREE.Mesh(
                new THREE.PlaneGeometry(10, 8),
                new THREE.MeshBasicMaterial({ color: 0xf8fafc })
            );
            keySoftbox.position.set(7, 8, 7);
            keySoftbox.lookAt(0, 0, 0);
            envScene.add(keySoftbox);

            // Cyan rim reflection panel
            const cyanSoftbox = new THREE.Mesh(
                new THREE.PlaneGeometry(8, 8),
                new THREE.MeshBasicMaterial({ color: 0x38bdf8 })
            );
            cyanSoftbox.position.set(-8, 4, -7);
            cyanSoftbox.lookAt(0, 0, 0);
            envScene.add(cyanSoftbox);

            // Dark floor reflector
            const floorReflector = new THREE.Mesh(
                new THREE.PlaneGeometry(20, 20),
                new THREE.MeshBasicMaterial({ color: 0x0b1329 })
            );
            floorReflector.position.set(0, -11.9, 0);
            floorReflector.rotation.x = -Math.PI / 2;
            envScene.add(floorReflector);

            const envTarget = pmremGenerator.fromScene(envScene, 0.04);
            scene.environment = envTarget.texture;
            pmremGenerator.dispose();
        } catch (e) {
            console.warn('RoomEnvironment PMREM generation bypassed:', e);
        }

        // 3. Grounding: ShadowMaterial Floor + Soft Cyan Radial Ground Glow
        const shadowFloor = new THREE.Mesh(
            new THREE.PlaneGeometry(16, 14),
            new THREE.ShadowMaterial({ opacity: 0.42 })
        );
        shadowFloor.rotation.x = -Math.PI / 2;
        shadowFloor.position.y = -0.405;
        shadowFloor.receiveShadow = true;
        scene.add(shadowFloor);

        // Procedural radial cyan glow texture for floor
        function generateFloorGlowTexture() {
            const glowCanvas = document.createElement('canvas');
            glowCanvas.width = 512;
            glowCanvas.height = 512;
            const ctx = glowCanvas.getContext('2d');
            const grad = ctx.createRadialGradient(256, 256, 15, 256, 256, 250);
            grad.addColorStop(0, 'rgba(34, 211, 238, 0.40)');
            grad.addColorStop(0.30, 'rgba(34, 211, 238, 0.20)');
            grad.addColorStop(0.60, 'rgba(56, 189, 248, 0.06)');
            grad.addColorStop(1, 'rgba(11, 18, 36, 0)');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, 512, 512);
            const tex = new THREE.CanvasTexture(glowCanvas);
            tex.generateMipmaps = true;
            return tex;
        }

        const floorGlowTex = generateFloorGlowTexture();
        const floorGlowMesh = new THREE.Mesh(
            new THREE.PlaneGeometry(7.5, 7.5),
            new THREE.MeshBasicMaterial({
                map: floorGlowTex,
                transparent: true,
                opacity: 0.32,
                blending: THREE.AdditiveBlending,
                depthWrite: false
            })
        );
        floorGlowMesh.rotation.x = -Math.PI / 2;
        floorGlowMesh.position.y = -0.40;
        scene.add(floorGlowMesh);

        // 4. Natural Lighting Rig (No overbright point lights on the PCB)
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.40);
        scene.add(ambientLight);

        // Directional Key Light with Soft Shadow
        const keyLight = new THREE.DirectionalLight(0xffffff, 1.95);
        keyLight.position.set(6.0, 10.0, 5.5);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.width = 2048;
        keyLight.shadow.mapSize.height = 2048;
        keyLight.shadow.camera.near = 0.5;
        keyLight.shadow.camera.far = 30;
        keyLight.shadow.camera.left = -4.5;
        keyLight.shadow.camera.right = 4.5;
        keyLight.shadow.camera.top = 4.5;
        keyLight.shadow.camera.bottom = -4.5;
        keyLight.shadow.bias = -0.0003;
        keyLight.shadow.radius = 2.4;
        scene.add(keyLight);

        // Cyan Rim Light (High Specular Edge Definition)
        const cyanRimLight = new THREE.DirectionalLight(0x22d3ee, 2.3);
        cyanRimLight.position.set(-6.0, 3.8, -4.5);
        scene.add(cyanRimLight);

        // Subtle warm/neutral fill light from below
        const fillLight = new THREE.DirectionalLight(0x94a3b8, 0.30);
        fillLight.position.set(0, -4, 3);
        scene.add(fillLight);

        // 5. RoundedBoxGeometry Helper (Bevel ~0.02)
        function createRoundedBox(w, h, d, bevel = 0.02) {
            const b = Math.min(bevel, w * 0.2, h * 0.2, d * 0.2);
            const shape = new THREE.Shape();
            const hw = w / 2 - b;
            const hh = h / 2 - b;
            shape.moveTo(-hw, hh);
            shape.lineTo(hw, hh);
            shape.lineTo(hw, -hh);
            shape.lineTo(-hw, -hh);
            shape.closePath();

            const extrudeSettings = {
                depth: d - b * 2,
                bevelEnabled: true,
                bevelSegments: 2,
                steps: 1,
                bevelSize: b,
                bevelThickness: b
            };
            const geo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
            geo.center();
            return geo;
        }

        // 6. Procedural Textures: PCB Color Map + Bump Map
        function generatePcbTextures() {
            // Color Map Canvas
            const cCanvas = document.createElement('canvas');
            cCanvas.width = 1024;
            cCanvas.height = 1024;
            const cCtx = cCanvas.getContext('2d');

            // Bump Map Canvas (Grayscale Height)
            const bCanvas = document.createElement('canvas');
            bCanvas.width = 1024;
            bCanvas.height = 1024;
            const bCtx = bCanvas.getContext('2d');

            // 1. Solder Mask Base: Deep Green #14532d
            cCtx.fillStyle = '#14532d';
            cCtx.fillRect(0, 0, 1024, 1024);

            bCtx.fillStyle = '#000000'; // Base depth
            bCtx.fillRect(0, 0, 1024, 1024);

            // Subtle copper ground pour pattern
            cCtx.fillStyle = '#166534';
            cCtx.fillRect(70, 70, 884, 884);
            bCtx.fillStyle = '#222222';
            bCtx.fillRect(70, 70, 884, 884);

            // 2. Copper Circuit Traces (Tracks with 45° angled routing)
            cCtx.strokeStyle = '#d97706';
            cCtx.lineWidth = 4;
            cCtx.lineCap = 'round';
            cCtx.lineJoin = 'round';

            bCtx.strokeStyle = '#777777'; // Raised trace relief
            bCtx.lineWidth = 4;
            bCtx.lineCap = 'round';
            bCtx.lineJoin = 'round';

            const tracePaths = [
                // CPU to DRAM buses
                [[512, 512], [650, 512], [700, 420], [820, 420]],
                [[512, 490], [640, 490], [680, 400], [820, 400]],
                [[512, 534], [640, 534], [680, 600], [820, 600]],
                [[512, 556], [650, 556], [700, 620], [820, 620]],
                // CPU to Ethernet & USB
                [[480, 512], [320, 512], [260, 380], [150, 380]],
                [[480, 490], [310, 490], [250, 360], [150, 360]],
                [[480, 534], [310, 534], [250, 660], [150, 660]],
                [[480, 556], [320, 556], [260, 680], [150, 680]],
                // GPIO Header traces
                [[512, 460], [512, 300], [600, 210], [780, 210]],
                [[490, 460], [490, 290], [580, 190], [780, 190]],
                [[534, 460], [534, 310], [620, 230], [780, 230]],
                // Power distribution rails
                [[250, 200], [350, 200], [420, 350], [420, 512]],
                [[250, 800], [380, 800], [420, 680], [420, 512]]
            ];

            tracePaths.forEach(path => {
                cCtx.beginPath();
                bCtx.beginPath();
                cCtx.moveTo(path[0][0], path[0][1]);
                bCtx.moveTo(path[0][0], path[0][1]);
                for (let j = 1; j < path.length; j++) {
                    cCtx.lineTo(path[j][0], path[j][1]);
                    bCtx.lineTo(path[j][0], path[j][1]);
                }
                cCtx.stroke();
                bCtx.stroke();
            });

            // 3. Vias: Golden circular rings with black drill hole centers
            const vias = [
                [700, 420], [680, 400], [700, 620], [680, 600],
                [260, 380], [250, 360], [260, 680], [250, 660],
                [600, 210], [580, 190], [620, 230], [420, 350],
                [420, 700], [550, 720], [360, 750], [720, 750],
                [180, 220], [200, 240], [840, 240], [820, 220],
                [400, 450], [620, 450], [400, 570], [620, 570]
            ];

            vias.forEach(v => {
                cCtx.fillStyle = '#f59e0b';
                cCtx.beginPath();
                cCtx.arc(v[0], v[1], 5, 0, Math.PI * 2);
                cCtx.fill();

                bCtx.fillStyle = '#aaaaaa';
                bCtx.beginPath();
                bCtx.arc(v[0], v[1], 5, 0, Math.PI * 2);
                bCtx.fill();

                cCtx.fillStyle = '#0a2215';
                cCtx.beginPath();
                cCtx.arc(v[0], v[1], 2, 0, Math.PI * 2);
                cCtx.fill();

                bCtx.fillStyle = '#000000';
                bCtx.beginPath();
                bCtx.arc(v[0], v[1], 2, 0, Math.PI * 2);
                bCtx.fill();
            });

            // 4. Surface Mount Pads (Gold metalness 1, roughness 0.25)
            cCtx.fillStyle = '#fbbf24';
            bCtx.fillStyle = '#bbbbbb';
            for (let x = 460; x <= 564; x += 16) {
                cCtx.fillRect(x, 436, 8, 14);
                cCtx.fillRect(x, 574, 8, 14);
                bCtx.fillRect(x, 436, 8, 14);
                bCtx.fillRect(x, 574, 8, 14);
            }
            for (let y = 460; y <= 564; y += 16) {
                cCtx.fillRect(436, y, 14, 8);
                cCtx.fillRect(574, y, 14, 8);
                bCtx.fillRect(436, y, 14, 8);
                bCtx.fillRect(574, y, 14, 8);
            }

            // 5. White Silkscreen Layer (Crisp White Text & Outlines)
            cCtx.fillStyle = '#ffffff';
            cCtx.strokeStyle = '#ffffff';
            cCtx.lineWidth = 2.5;

            bCtx.fillStyle = '#ffffff'; // Silkscreen sits highest on the PCB
            bCtx.strokeStyle = '#ffffff';
            bCtx.lineWidth = 2.5;

            // SoC Component Outline
            cCtx.strokeRect(436, 436, 152, 152);
            bCtx.strokeRect(436, 436, 152, 152);

            // Memory Outlines
            cCtx.strokeRect(710, 360, 120, 150);
            cCtx.strokeRect(710, 540, 120, 150);
            bCtx.strokeRect(710, 360, 120, 150);
            bCtx.strokeRect(710, 540, 120, 150);

            // GPIO Header Outline
            cCtx.strokeRect(580, 150, 260, 60);
            bCtx.strokeRect(580, 150, 260, 60);

            // Silkscreen Typography
            cCtx.font = 'bold 20px monospace';
            cCtx.fillText('ELECTRODESK SBC-V2', 120, 135);
            cCtx.font = '13px monospace';
            cCtx.fillText('MODEL 4B // 64-BIT OCTA-CORE', 120, 160);
            cCtx.fillText('REV 3.1 // 2026', 120, 180);
            cCtx.fillText('U1 SoC', 485, 426);
            cCtx.fillText('U2 DRAM', 730, 350);
            cCtx.fillText('U3 FLASH', 730, 715);
            cCtx.fillText('USB 3.0', 100, 780);
            cCtx.fillText('GbE LAN', 100, 310);
            cCtx.fillText('GPIO 40-PIN', 640, 140);
            cCtx.fillText('PIN 1', 580, 140);

            bCtx.font = 'bold 20px monospace';
            bCtx.fillText('ELECTRODESK SBC-V2', 120, 135);
            bCtx.font = '13px monospace';
            bCtx.fillText('MODEL 4B // 64-BIT OCTA-CORE', 120, 160);
            bCtx.fillText('REV 3.1 // 2026', 120, 180);
            bCtx.fillText('U1 SoC', 485, 426);
            bCtx.fillText('U2 DRAM', 730, 350);
            bCtx.fillText('U3 FLASH', 730, 715);
            bCtx.fillText('USB 3.0', 100, 780);
            bCtx.fillText('GbE LAN', 100, 310);
            bCtx.fillText('GPIO 40-PIN', 640, 140);
            bCtx.fillText('PIN 1', 580, 140);

            const maxAnisotropy = (renderer && renderer.capabilities) ? renderer.capabilities.getMaxAnisotropy() : 4;

            const cTex = new THREE.CanvasTexture(cCanvas);
            cTex.generateMipmaps = true;
            cTex.minFilter = THREE.LinearMipmapLinearFilter;
            cTex.magFilter = THREE.LinearFilter;
            cTex.anisotropy = maxAnisotropy;

            const bTex = new THREE.CanvasTexture(bCanvas);
            bTex.generateMipmaps = true;
            bTex.minFilter = THREE.LinearMipmapLinearFilter;
            bTex.magFilter = THREE.LinearFilter;
            bTex.anisotropy = maxAnisotropy;

            return { colorMap: cTex, bumpMap: bTex };
        }

        const { colorMap: pcbColorMap, bumpMap: pcbBumpMap } = generatePcbTextures();

        // 7. Chip Laser-Engraved Procedural Textures
        function generateChipMarkingTexture(line1, line2, line3) {
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 512;
            const ctx = canvas.getContext('2d');

            // Near-black IC package body #15181c
            ctx.fillStyle = '#15181c';
            ctx.fillRect(0, 0, 512, 512);

            // Laser-engraved silver/gray typography
            ctx.fillStyle = '#94a3b8';
            ctx.font = 'bold 36px monospace';
            ctx.fillText(line1, 60, 180);
            ctx.font = '24px monospace';
            ctx.fillStyle = '#64748b';
            ctx.fillText(line2, 60, 240);
            ctx.fillText(line3, 60, 280);

            // Pin 1 laser-etched dot
            ctx.fillStyle = '#475569';
            ctx.beginPath();
            ctx.arc(60, 60, 14, 0, Math.PI * 2);
            ctx.fill();

            // 2D DataMatrix code in corner
            ctx.fillStyle = '#94a3b8';
            for (let r = 0; r < 6; r++) {
                for (let c = 0; c < 6; c++) {
                    if ((r + c) % 2 === 0 || (r === 0 && c === 5) || (r === 5 && c === 0)) {
                        ctx.fillRect(360 + c * 14, 60 + r * 14, 11, 11);
                    }
                }
            }

            const maxAnisotropy = (renderer && renderer.capabilities) ? renderer.capabilities.getMaxAnisotropy() : 4;
            const tex = new THREE.CanvasTexture(canvas);
            tex.generateMipmaps = true;
            tex.minFilter = THREE.LinearMipmapLinearFilter;
            tex.magFilter = THREE.LinearFilter;
            tex.anisotropy = maxAnisotropy;
            return tex;
        }

        const cpuMarkingTex = generateChipMarkingTexture('ELECTRODESK', 'EDK-9900PRO // 64-BIT', 'ARM CORTEX-A78 // 2.8GHz');
        const ramMarkingTex = generateChipMarkingTexture('ELECTRODESK', 'DRAM LPDDR5X 16GB', '8533 Mbps // SEC-2440');

        // 8. PBR Material Library
        const materials = {
            standoffBlack: new THREE.MeshStandardMaterial({
                color: 0x18181b,
                metalness: 0.82,
                roughness: 0.32
            }),
            // Pale base substrate sheet: transparency opacity ~0.85
            basePlate: new THREE.MeshStandardMaterial({
                color: 0xf1f5f9,
                metalness: 0.12,
                roughness: 0.40,
                transparent: true,
                opacity: 0.85
            }),
            copperTrace: new THREE.MeshStandardMaterial({
                color: 0xe08238,
                metalness: 1.0,
                roughness: 0.25
            }),
            goldPad: new THREE.MeshStandardMaterial({
                color: 0xf59e0b,
                metalness: 1.0,
                roughness: 0.25
            }),
            // Deep Green #14532d, MeshPhysicalMaterial with lower bumpScale to eliminate aliasing
            pcbGreenClearcoat: new THREE.MeshPhysicalMaterial({
                color: 0x14532d,
                map: pcbColorMap,
                bumpMap: pcbBumpMap,
                bumpScale: 0.005,
                roughness: 0.45,
                metalness: 0.0,
                clearcoat: 0.70,
                clearcoatRoughness: 0.12
            }),
            // Chips near-black #15181c with canvas-engraved markings (no tint)
            chipCpu: new THREE.MeshStandardMaterial({
                color: 0x15181c,
                map: cpuMarkingTex,
                metalness: 0.05,
                roughness: 0.70
            }),
            chipRam: new THREE.MeshStandardMaterial({
                color: 0x15181c,
                map: ramMarkingTex,
                metalness: 0.05,
                roughness: 0.70
            }),
            chipMatte: new THREE.MeshStandardMaterial({
                color: 0x15181c,
                metalness: 0.05,
                roughness: 0.70
            }),
            // Aluminum heatsink with 14 fins
            heatsinkAluminum: new THREE.MeshStandardMaterial({
                color: 0xd1d5db,
                metalness: 0.92,
                roughness: 0.25
            }),
            // Brushed steel ports: metalness 1, roughness 0.35, envMapIntensity 1.2
            portBrushedSteel: new THREE.MeshStandardMaterial({
                color: 0xcbd5e1,
                metalness: 1.0,
                roughness: 0.35,
                envMapIntensity: 1.2
            }),
            portInteriorDark: new THREE.MeshStandardMaterial({
                color: 0x07090e,
                roughness: 0.88,
                metalness: 0.10
            }),
            portTongueBlue: new THREE.MeshStandardMaterial({
                color: 0x0077d4, // Vivid USB 3.0 Blue
                roughness: 0.40,
                metalness: 0.05
            }),
            pinGold: new THREE.MeshStandardMaterial({
                color: 0xf59e0b,
                metalness: 1.0,
                roughness: 0.25
            }),
            headerBaseBlack: new THREE.MeshStandardMaterial({
                color: 0x15181c,
                roughness: 0.85
            }),
            smdCapacitor: new THREE.MeshStandardMaterial({
                color: 0x854d0e,
                metalness: 0.65,
                roughness: 0.30
            }),
            screwSteel: new THREE.MeshStandardMaterial({
                color: 0xcfd8dc,
                metalness: 0.95,
                roughness: 0.18
            }),
            ledCyan: new THREE.MeshStandardMaterial({
                color: 0x22d3ee,
                emissive: 0x22d3ee,
                emissiveIntensity: 0.85,
                roughness: 0.25
            }),
            ledAmber: new THREE.MeshStandardMaterial({
                color: 0xfbbf24,
                emissive: 0xd97706,
                emissiveIntensity: 0.60,
                roughness: 0.25
            })
        };

        // 9. Root Board Group (Increased by 25% and centered)
        const boardRoot = new THREE.Group();
        boardRoot.scale.set(1.25, 1.25, 1.25);
        boardRoot.rotation.x = 0.22;
        boardRoot.rotation.y = -0.48;
        scene.add(boardRoot);

        // Staggered Layer System for Bottom-to-Top Assembly
        const layers = [];

        function addLayer(group, explodedY, assembledY, startFrac, endFrac, options = {}) {
            group.position.y = prefersReducedMotion ? assembledY : explodedY;
            boardRoot.add(group);
            layers.push({
                group: group,
                explodedY: explodedY,
                assembledY: assembledY,
                startFrac: startFrac,
                endFrac: endFrac,
                rotatesY: options.rotatesY || false,
                initialRotY: group.rotation.y,
                turns: options.turns || 0
            });
            return group;
        }

        const cornerPositions = [
            { x: -1.85, z: -1.22 },
            { x:  1.85, z: -1.22 },
            { x: -1.85, z:  1.22 },
            { x:  1.85, z:  1.22 }
        ];

        // --- LAYER 1: Four Black Standoff Feet ---
        const standoffsGroup = new THREE.Group();
        cornerPositions.forEach(pos => {
            const foot = new THREE.Mesh(
                new THREE.CylinderGeometry(0.14, 0.14, 0.32, 24),
                materials.standoffBlack
            );
            foot.position.set(pos.x, 0, pos.z);
            foot.castShadow = true;
            foot.receiveShadow = true;
            standoffsGroup.add(foot);
        });
        addLayer(standoffsGroup, -1.8, -0.16, 0.00, 0.50);

        // --- LAYER 2: Pale Base Substrate Sheet (RoundedBox with 0.02 bevel) ---
        const baseSheetGroup = new THREE.Group();
        const baseSheet = new THREE.Mesh(
            createRoundedBox(4.2, 0.04, 2.8, 0.02),
            materials.basePlate
        );
        baseSheet.castShadow = true;
        baseSheet.receiveShadow = true;
        baseSheetGroup.add(baseSheet);

        cornerPositions.forEach(pos => {
            const pad = new THREE.Mesh(
                new THREE.CylinderGeometry(0.20, 0.20, 0.045, 16),
                materials.copperTrace
            );
            pad.position.set(pos.x, 0, pos.z);
            baseSheetGroup.add(pad);
        });
        addLayer(baseSheetGroup, -1.0, -0.02, 0.08, 0.62);

        // --- LAYER 3: Copper Traces & Ground Plane ---
        const copperLayerGroup = new THREE.Group();
        const socPad = new THREE.Mesh(
            createRoundedBox(1.2, 0.015, 1.2, 0.01),
            materials.copperTrace
        );
        copperLayerGroup.add(socPad);

        const copperTracks = [
            { x: 0.5, z: -0.4, w: 1.4, d: 0.04 },
            { x: 0.5, z:  0.4, w: 1.4, d: 0.04 },
            { x: -0.8, z: 0.0, w: 0.04, d: 1.6 },
            { x: -1.6, z:  0.85, w: 0.7, d: 0.8 },
            { x: -1.6, z: -0.55, w: 0.7, d: 0.8 },
            { x:  0.6, z:  1.15, w: 1.7, d: 0.25 }
        ];
        copperTracks.forEach(t => {
            const tr = new THREE.Mesh(new THREE.BoxGeometry(t.w, 0.014, t.d), materials.copperTrace);
            tr.position.set(t.x, 0, t.z);
            copperLayerGroup.add(tr);
        });
        cornerPositions.forEach(pos => {
            const ring = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.016, 16), materials.goldPad);
            ring.position.set(pos.x, 0, pos.z);
            copperLayerGroup.add(ring);
        });
        addLayer(copperLayerGroup, 0.35, 0.02, 0.18, 0.72);

        // --- LAYER 4: Deep Green #14532d PCB (MeshPhysicalMaterial with Clearcoat & BumpMap) ---
        const pcbGroup = new THREE.Group();
        const pcbBoard = new THREE.Mesh(
            createRoundedBox(4.2, 0.06, 2.8, 0.02),
            materials.pcbGreenClearcoat
        );
        pcbBoard.castShadow = true;
        pcbBoard.receiveShadow = true;
        pcbGroup.add(pcbBoard);
        addLayer(pcbGroup, 1.4, 0.06, 0.26, 0.80);

        // --- LAYER 5: 60 Tiny SMD Resistors & Capacitors (InstancedMesh) ---
        const smdCount = 60;
        const smdGeo = createRoundedBox(0.12, 0.05, 0.07, 0.01);
        const smdInstanced = new THREE.InstancedMesh(smdGeo, materials.smdCapacitor, smdCount);
        smdInstanced.castShadow = true;
        smdInstanced.receiveShadow = true;

        const dummy = new THREE.Object3D();
        let idx = 0;

        // Decoupling bypass ring around CPU
        for (let x = -0.7; x <= 0.7; x += 0.22) {
            dummy.position.set(x, 0.09, -0.68);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);

            dummy.position.set(x, 0.09, 0.68);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);
        }

        // Filtering capacitors around DRAM
        for (let z = -0.75; z <= 0.75; z += 0.18) {
            dummy.position.set(1.24, 0.09, z);
            dummy.rotation.y = Math.PI / 2;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);
        }

        // Power rail bank near USB/Ethernet
        for (let z = -0.3; z <= 0.55; z += 0.15) {
            dummy.position.set(-1.12, 0.09, z);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);

            dummy.position.set(-0.95, 0.09, z);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);
        }

        // Fill remaining instances across voltage regulators
        while (idx < smdCount) {
            dummy.position.set(-0.45 + (idx % 5) * 0.18, 0.09, -0.88);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);
        }
        smdInstanced.instanceMatrix.needsUpdate = true;

        const smdGroup = new THREE.Group();
        smdGroup.add(smdInstanced);
        addLayer(smdGroup, 2.5, 0.03, 0.34, 0.86);

        // --- LAYER 6: IC Chips (Canvas-Engraved), Brushed Steel Ports & Pin Header ---
        const compGroup = new THREE.Group();

        // Central SoC (Near-Black #15181c with Laser-Engraved Markings)
        const cpuPkg = new THREE.Mesh(
            createRoundedBox(1.02, 0.10, 1.02, 0.02),
            materials.chipCpu
        );
        cpuPkg.castShadow = true;
        cpuPkg.receiveShadow = true;
        compGroup.add(cpuPkg);

        const cpuStatusLed = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.04, 0.08), materials.ledCyan);
        cpuStatusLed.position.set(0.34, 0.065, 0.34);
        compGroup.add(cpuStatusLed);

        // DRAM Memory ICs (Laser-Engraved)
        [-0.42, 0.42].forEach(z => {
            const ram = new THREE.Mesh(
                createRoundedBox(0.55, 0.08, 0.74, 0.02),
                materials.chipRam
            );
            ram.position.set(0.85, 0, z);
            ram.castShadow = true;
            compGroup.add(ram);
        });

        // Stacked Dual USB 3.0 Housing (Brushed Steel with Blue USB3 Tongues & Dark Cavities)
        const usbBlock = new THREE.Mesh(
            createRoundedBox(0.70, 0.56, 0.78, 0.02),
            materials.portBrushedSteel
        );
        usbBlock.castShadow = true;
        usbBlock.receiveShadow = true;

        [-0.13, 0.13].forEach(yOff => {
            // Dark interior cavity slot
            const usbCavity = new THREE.Mesh(
                new THREE.BoxGeometry(0.24, 0.18, 0.54),
                materials.portInteriorDark
            );
            usbCavity.position.set(-0.25, yOff, 0);
            usbBlock.add(usbCavity);

            // Blue USB 3.0 Tongue inside the dark cavity
            const tongue = new THREE.Mesh(
                new THREE.BoxGeometry(0.18, 0.04, 0.42),
                materials.portTongueBlue
            );
            tongue.position.set(-0.27, yOff - 0.045, 0);
            usbBlock.add(tongue);

            // 4 Tiny Gold Contact Pins on the tongue
            for (let p = 0; p < 4; p++) {
                const pin = new THREE.Mesh(
                    new THREE.BoxGeometry(0.12, 0.012, 0.045),
                    materials.pinGold
                );
                pin.position.set(-0.27, yOff - 0.02, -0.15 + p * 0.10);
                usbBlock.add(pin);
            }
        });
        usbBlock.position.set(-1.62, 0.20, 0.85);
        compGroup.add(usbBlock);

        // RJ-45 Gigabit Ethernet Housing (Brushed Steel) with Dark Interior & Status LEDs
        const ethBlock = new THREE.Mesh(
            createRoundedBox(0.76, 0.60, 0.84, 0.02),
            materials.portBrushedSteel
        );
        ethBlock.castShadow = true;
        ethBlock.receiveShadow = true;

        // Dark Interior Cavity on the Ethernet Jack
        const ethCavity = new THREE.Mesh(
            new THREE.BoxGeometry(0.28, 0.44, 0.64),
            materials.portInteriorDark
        );
        ethCavity.position.set(-0.26, -0.04, 0);
        ethBlock.add(ethCavity);

        // 8 Tiny Angled Gold Contact Wires inside Ethernet interior
        for (let i = 0; i < 8; i++) {
            const wire = new THREE.Mesh(
                new THREE.CylinderGeometry(0.008, 0.008, 0.14, 8),
                materials.pinGold
            );
            wire.rotation.z = Math.PI / 4;
            wire.position.set(-0.28, 0.10, -0.21 + i * 0.06);
            ethBlock.add(wire);
        }

        // Ethernet clip tab cutout detail at bottom
        const ethTab = new THREE.Mesh(
            new THREE.BoxGeometry(0.14, 0.08, 0.22),
            materials.portInteriorDark
        );
        ethTab.position.set(-0.32, -0.24, 0);
        ethBlock.add(ethTab);

        // RJ-45 Activity & Link Status LEDs
        const ethLed1 = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.06, 0.06), materials.ledCyan);
        ethLed1.position.set(-0.38, 0.24, -0.24);
        ethBlock.add(ethLed1);
        const ethLed2 = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.06, 0.06), materials.ledAmber);
        ethLed2.position.set(-0.38, 0.24, 0.24);
        ethBlock.add(ethLed2);

        ethBlock.position.set(-1.62, 0.22, -0.55);
        compGroup.add(ethBlock);

        // HDMI Output Port (Brushed Steel with Dark Interior)
        const hdmiPort = new THREE.Mesh(
            createRoundedBox(0.56, 0.22, 0.40, 0.02),
            materials.portBrushedSteel
        );
        hdmiPort.position.set(0.35, 0.06, -1.25);
        hdmiPort.castShadow = true;

        const hdmiCavity = new THREE.Mesh(
            new THREE.BoxGeometry(0.38, 0.10, 0.18),
            materials.portInteriorDark
        );
        hdmiCavity.position.set(0, 0, -0.12);
        hdmiPort.add(hdmiCavity);
        compGroup.add(hdmiPort);

        // USB-C Power/Data Port (Brushed Steel with Dark Interior)
        const usbcPort = new THREE.Mesh(
            createRoundedBox(0.38, 0.16, 0.24, 0.02),
            materials.portBrushedSteel
        );
        usbcPort.position.set(-0.65, 0.06, -1.28);
        usbcPort.castShadow = true;

        const usbcCavity = new THREE.Mesh(
            new THREE.BoxGeometry(0.24, 0.06, 0.12),
            materials.portInteriorDark
        );
        usbcCavity.position.set(0, 0, -0.07);
        usbcPort.add(usbcCavity);
        compGroup.add(usbcPort);

        // 40-Pin GPIO Header Strip (Dual-Row Gold Pins: Metalness 1, Roughness 0.25)
        const gpioBase = new THREE.Mesh(
            createRoundedBox(1.68, 0.12, 0.24, 0.01),
            materials.headerBaseBlack
        );
        gpioBase.position.set(0.65, 0.06, 1.15);
        gpioBase.castShadow = true;
        compGroup.add(gpioBase);

        for (let x = -0.72; x <= 0.72; x += 0.18) {
            [-0.06, 0.06].forEach(z => {
                const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.024, 0.024, 0.38, 12), materials.pinGold);
                pin.position.set(0.65 + x, 0.25, 1.15 + z);
                pin.castShadow = true;
                compGroup.add(pin);
            });
        }

        addLayer(compGroup, 2.9, 0.14, 0.40, 0.92);

        // --- LAYER 7: Extruded Aluminum Heatsink with 14 Thin Fins ---
        const heatsinkGroup = new THREE.Group();
        const hsBase = new THREE.Mesh(
            createRoundedBox(1.08, 0.06, 1.08, 0.015),
            materials.heatsinkAluminum
        );
        hsBase.castShadow = true;
        hsBase.receiveShadow = true;
        heatsinkGroup.add(hsBase);

        // 14 thin extruded cooling fins (aluminum metalness 0.92, roughness 0.25)
        const finCount = 14;
        const finSpacing = 0.96 / (finCount - 1);
        for (let i = 0; i < finCount; i++) {
            const fX = -0.48 + i * finSpacing;
            const fin = new THREE.Mesh(
                new THREE.BoxGeometry(0.022, 0.38, 1.04),
                materials.heatsinkAluminum
            );
            fin.position.set(fX, 0.22, 0);
            fin.castShadow = true;
            fin.receiveShadow = true;
            heatsinkGroup.add(fin);
        }
        heatsinkGroup.position.set(0, 0, 0);
        addLayer(heatsinkGroup, 3.6, 0.28, 0.48, 0.96);

        // --- LAYER 8: 4 Corner Screws (Tightening with spin) ---
        cornerPositions.forEach(pos => {
            const screwGroup = new THREE.Group();
            const screwHead = new THREE.Mesh(
                new THREE.CylinderGeometry(0.14, 0.13, 0.07, 16),
                materials.screwSteel
            );
            screwHead.position.set(0, 0.035, 0);
            screwHead.castShadow = true;
            screwGroup.add(screwHead);

            const slot1 = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.02, 0.04), materials.chipMatte);
            slot1.position.set(0, 0.075, 0);
            screwGroup.add(slot1);
            const slot2 = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.02, 0.18), materials.chipMatte);
            slot2.position.set(0, 0.075, 0);
            screwGroup.add(slot2);

            const shank = new THREE.Mesh(
                new THREE.CylinderGeometry(0.05, 0.05, 0.28, 8),
                materials.screwSteel
            );
            shank.position.set(0, -0.12, 0);
            shank.castShadow = true;
            screwGroup.add(shank);

            screwGroup.position.set(pos.x, 0, pos.z);
            addLayer(screwGroup, 4.4, 0.13, 0.54, 1.00, {
                rotatesY: true,
                turns: 6.0
            });
        });

        // 10. Animation & Lifecycle
        const START_DELAY_MS = 800;    // ~0.8s exploded float
        const ANIM_DURATION_MS = 3000; // ~3.0s assembly duration
        const startTime = performance.now();

        let isAssembled = prefersReducedMotion;
        let assemblyFinishTime = prefersReducedMotion ? startTime : 0;
        let isRunning = true;
        let isPoweringOn = false;

        function easeInOutCubic(t) {
            return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
        }

        // Parallax Tracking
        const mouseTarget = { x: 0, y: 0 };
        const mouseCurrent = { x: 0, y: 0 };

        function onMouseMove(e) {
            const nx = (e.clientX / window.innerWidth) - 0.5;
            const ny = (e.clientY / window.innerHeight) - 0.5;
            mouseTarget.x = nx * 0.35;
            mouseTarget.y = ny * 0.25;
        }
        window.addEventListener('mousemove', onMouseMove, { passive: true });

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

        document.addEventListener('visibilitychange', () => {
            isRunning = !document.hidden;
            if (isRunning) requestAnimationFrame(renderLoop);
        });

        function renderLoop(now) {
            if (!isRunning) return;

            if (container && container.clientWidth > 0 && container.clientHeight > 0) {
                if (Math.abs(container.clientWidth - width) > 8 || Math.abs(container.clientHeight - height) > 8) {
                    onWindowResize();
                }
            }

            const elapsed = now - startTime;

            // Staggered Bottom-to-Top Assembly
            if (!prefersReducedMotion) {
                if (elapsed < START_DELAY_MS) {
                    if (statusText) statusText.textContent = 'EXPLODED VIEW // STANDBY';
                } else if (elapsed < START_DELAY_MS + ANIM_DURATION_MS) {
                    const overallProgress = (elapsed - START_DELAY_MS) / ANIM_DURATION_MS;

                    layers.forEach(layer => {
                        const localRaw = (overallProgress - layer.startFrac) / (layer.endFrac - layer.startFrac);
                        const localClamped = Math.min(Math.max(localRaw, 0), 1);
                        const progress = easeInOutCubic(localClamped);

                        layer.group.position.y = layer.explodedY + (layer.assembledY - layer.explodedY) * progress;
                        if (layer.rotatesY) {
                            layer.group.rotation.y = layer.initialRotY + (layer.turns * Math.PI * 2 * progress);
                        }
                    });

                    if (statusText) statusText.textContent = 'ASSEMBLING CIRCUIT BOARD...';
                } else if (!isAssembled) {
                    isAssembled = true;
                    assemblyFinishTime = now;

                    layers.forEach(layer => {
                        layer.group.position.y = layer.assembledY;
                        if (layer.rotatesY) {
                            layer.group.rotation.y = layer.initialRotY + (layer.turns * Math.PI * 2);
                        }
                    });

                    if (statusText) statusText.textContent = 'ELECTRODESK HARDWARE ASSEMBLED';
                }
            }

            // Post-Assembly Subtle LED Blink & Idle Motion
            if (isAssembled) {
                const idleTime = (now - assemblyFinishTime) * 0.001;

                // Status text update right after assembly
                if (idleTime < 1.6) {
                    const pulseT = idleTime / 1.6;
                    materials.ledCyan.emissiveIntensity = 0.85 + Math.sin(pulseT * Math.PI * 4) * 1.5;
                    materials.ledAmber.emissiveIntensity = 0.5 + Math.cos(pulseT * Math.PI * 4) * 1.2;
                    if (statusText && idleTime > 0.8) {
                        statusText.textContent = 'ELECTRODESK SBC ONLINE // ALL SYSTEMS NOMINAL';
                    }
                } else if (!isPoweringOn) {
                    materials.ledCyan.emissiveIntensity = 0.70 + 0.35 * Math.sin(idleTime * 3.0);
                }

                // Smooth idle float, gentle sway & mouse parallax
                boardRoot.position.y = Math.sin(idleTime * 1.15) * 0.07;

                mouseCurrent.x += (mouseTarget.x - mouseCurrent.x) * 0.045;
                mouseCurrent.y += (mouseTarget.y - mouseCurrent.y) * 0.045;

                boardRoot.rotation.y = -0.48 + Math.sin(idleTime * 0.32) * 0.06 + mouseCurrent.x;
                boardRoot.rotation.x =  0.22 + Math.cos(idleTime * 0.42) * 0.03 + mouseCurrent.y;
            }

            renderer.render(scene, camera);
            requestAnimationFrame(renderLoop);
        }

        requestAnimationFrame(renderLoop);

        // 11. Login Submit Power-On Flash
        window.triggerBoardPowerOn = function (callback) {
            if (isPoweringOn) {
                if (callback) callback();
                return;
            }
            isPoweringOn = true;

            if (statusText) statusText.textContent = 'SYSTEM POWERING ON...';

            const overlay = document.getElementById('login-poweron-overlay');
            if (overlay) overlay.classList.add('login-poweron-active');

            materials.ledCyan.emissiveIntensity = 4.5;
            materials.ledCyan.emissive.setHex(0x38bdf8);

            camera.position.z -= 0.35;
            camera.position.y += 0.15;

            setTimeout(() => {
                if (callback) callback();
            }, 440);
        };

        // 12. Resource Disposal on Unload (Performance)
        function disposeScene() {
            isRunning = false;
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('resize', onWindowResize);

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

            if (pcbColorMap) pcbColorMap.dispose();
            if (pcbBumpMap) pcbBumpMap.dispose();
            if (cpuMarkingTex) cpuMarkingTex.dispose();
            if (ramMarkingTex) ramMarkingTex.dispose();
            if (floorGlowTex) floorGlowTex.dispose();

            if (renderer) {
                renderer.dispose();
                renderer.forceContextLoss();
            }
        }

        window.addEventListener('beforeunload', disposeScene);
    }

    window.initLoginScene = initScene;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initScene);
    } else {
        initScene();
    }
    window.addEventListener('load', initScene);
})();
