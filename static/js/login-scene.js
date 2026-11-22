/**
 * Electrodesk - Photorealistic 3D Exploded Circuit Board Intro Scene
 * Built strictly with Three.js BoxGeometry & CylinderGeometry.
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

        // WebGL Fallback handling
        if (!isWebGLAvailable()) {
            console.warn('WebGL is not supported in this browser. Falling back to gradient studio background.');
            if (statusText) statusText.textContent = 'HARDWARE GRAPHICS ACCELERATION DISABLED';
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
        camera.position.set(5.0, 4.4, 5.5);
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
        renderer.setClearColor(0x000000, 0); // 100% transparent to blend with studio gradient

        // Tone Mapping & Color Management
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.15;

        // Soft Shadows
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;

        // 2. Procedural RoomEnvironment for Photorealistic PBR Reflections
        try {
            const pmremGenerator = new THREE.PMREMGenerator(renderer);
            pmremGenerator.compileEquirectangularShader();

            const envScene = new THREE.Scene();
            const envBox = new THREE.Mesh(
                new THREE.BoxGeometry(20, 20, 20),
                new THREE.MeshBasicMaterial({ color: 0x050814, side: THREE.BackSide })
            );
            envScene.add(envBox);

            // Overhead soft white studio softbox
            const softboxTop = new THREE.Mesh(
                new THREE.PlaneGeometry(8, 8),
                new THREE.MeshBasicMaterial({ color: 0xffffff })
            );
            softboxTop.position.set(2, 8, 3);
            softboxTop.lookAt(0, 0, 0);
            envScene.add(softboxTop);

            // Cyan accent rim softbox
            const softboxCyan = new THREE.Mesh(
                new THREE.PlaneGeometry(6, 6),
                new THREE.MeshBasicMaterial({ color: 0x38bdf8 })
            );
            softboxCyan.position.set(-6, 3, -5);
            softboxCyan.lookAt(0, 0, 0);
            envScene.add(softboxCyan);

            // Warm copper floor reflection
            const softboxWarm = new THREE.Mesh(
                new THREE.PlaneGeometry(8, 4),
                new THREE.MeshBasicMaterial({ color: 0xd97706 })
            );
            softboxWarm.position.set(0, -6, 2);
            softboxWarm.lookAt(0, 0, 0);
            envScene.add(softboxWarm);

            const envTarget = pmremGenerator.fromScene(envScene, 0.04);
            scene.environment = envTarget.texture;
        } catch (e) {
            console.warn('Procedural PMREM environment generation bypassed:', e);
        }

        // 3. Shadow-Catcher Floor
        const shadowFloor = new THREE.Mesh(
            new THREE.PlaneGeometry(12, 10),
            new THREE.ShadowMaterial({ opacity: 0.45 })
        );
        shadowFloor.rotation.x = -Math.PI / 2;
        shadowFloor.position.y = -0.36;
        shadowFloor.receiveShadow = true;
        scene.add(shadowFloor);

        // 4. Lighting Rig
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
        scene.add(ambientLight);

        // Directional Key Light with Soft Shadow
        const keyLight = new THREE.DirectionalLight(0xffffff, 2.2);
        keyLight.position.set(5.5, 9.0, 5.0);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.width = 1024;
        keyLight.shadow.mapSize.height = 1024;
        keyLight.shadow.camera.near = 0.5;
        keyLight.shadow.camera.far = 25;
        keyLight.shadow.camera.left = -3.8;
        keyLight.shadow.camera.right = 3.8;
        keyLight.shadow.camera.top = 3.8;
        keyLight.shadow.camera.bottom = -3.8;
        keyLight.shadow.bias = -0.0004;
        keyLight.shadow.radius = 2.4;
        scene.add(keyLight);

        // Cyan Rim Light (High specular edge definition)
        const cyanRimLight = new THREE.DirectionalLight(0x22d3ee, 2.6);
        cyanRimLight.position.set(-6.0, 3.8, -4.5);
        scene.add(cyanRimLight);

        // Warm Copper Fill Light
        const copperFillLight = new THREE.PointLight(0xf59e0b, 1.2, 14);
        copperFillLight.position.set(2.0, -1.5, 2.0);
        scene.add(copperFillLight);

        // Cyan Power-Pulse Traveling Light
        const powerPulseLight = new THREE.PointLight(0x22d3ee, 0.0, 10);
        powerPulseLight.position.set(0, 0.8, 0);
        scene.add(powerPulseLight);

        // 5. Procedural PCB Canvas Texture (Traces, Vias & Silkscreen)
        function generateProceduralPcbTexture() {
            const texCanvas = document.createElement('canvas');
            texCanvas.width = 1024;
            texCanvas.height = 1024;
            const ctx = texCanvas.getContext('2d');

            // Deep Emerald Green Solder Mask Base
            ctx.fillStyle = '#08482d';
            ctx.fillRect(0, 0, 1024, 1024);

            // Subtle PCB Fiber/Grid Weave Noise
            ctx.fillStyle = 'rgba(10, 85, 52, 0.4)';
            for (let i = 0; i < 1024; i += 8) {
                ctx.fillRect(i, 0, 2, 1024);
                ctx.fillRect(0, i, 1024, 2);
            }

            // Ground plane copper pour shapes
            ctx.fillStyle = '#105e3b';
            ctx.beginPath();
            ctx.rect(60, 60, 904, 904);
            ctx.fill();

            // Copper Circuit Traces (Metallic Gold / Copper lines with 45° bends)
            ctx.strokeStyle = '#c68434';
            ctx.lineWidth = 4;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';

            const traces = [
                // CPU to Memory bus lines
                [[512, 512], [650, 512], [700, 420], [800, 420]],
                [[512, 490], [640, 490], [680, 400], [800, 400]],
                [[512, 534], [640, 534], [680, 600], [800, 600]],
                [[512, 556], [650, 556], [700, 620], [800, 620]],
                // CPU to Ethernet & USB
                [[480, 512], [320, 512], [260, 380], [160, 380]],
                [[480, 490], [310, 490], [250, 360], [160, 360]],
                [[480, 534], [310, 534], [250, 660], [160, 660]],
                [[480, 556], [320, 556], [260, 680], [160, 680]],
                // GPIO Header traces
                [[512, 460], [512, 300], [600, 210], [780, 210]],
                [[490, 460], [490, 290], [580, 190], [780, 190]],
                [[534, 460], [534, 310], [620, 230], [780, 230]],
                // Power distribution bus
                [[250, 200], [350, 200], [420, 350], [420, 512]]
            ];

            traces.forEach(path => {
                ctx.beginPath();
                ctx.moveTo(path[0][0], path[0][1]);
                for (let j = 1; j < path.length; j++) {
                    ctx.lineTo(path[j][0], path[j][1]);
                }
                ctx.stroke();
            });

            // Vias (Golden circular rings with dark hole centers)
            const vias = [
                [700, 420], [680, 400], [700, 620], [680, 600],
                [260, 380], [250, 360], [260, 680], [250, 660],
                [600, 210], [580, 190], [620, 230], [420, 350],
                [420, 700], [550, 720], [360, 750], [720, 750],
                [180, 220], [200, 240], [840, 240], [820, 220]
            ];

            vias.forEach(v => {
                ctx.fillStyle = '#eab308';
                ctx.beginPath();
                ctx.arc(v[0], v[1], 5, 0, Math.PI * 2);
                ctx.fill();

                ctx.fillStyle = '#051810';
                ctx.beginPath();
                ctx.arc(v[0], v[1], 2, 0, Math.PI * 2);
                ctx.fill();
            });

            // Golden Surface Mount Contact Pads
            ctx.fillStyle = '#f59e0b';
            for (let x = 460; x <= 564; x += 16) {
                ctx.fillRect(x, 440, 8, 12);
                ctx.fillRect(x, 572, 8, 12);
            }
            for (let y = 460; y <= 564; y += 16) {
                ctx.fillRect(440, y, 12, 8);
                ctx.fillRect(572, y, 12, 8);
            }

            // White Silkscreen Layer (Markings, Labels, Boundaries)
            ctx.strokeStyle = '#f8fafc';
            ctx.fillStyle = '#f8fafc';
            ctx.lineWidth = 2.5;

            // SoC Component Outline
            ctx.strokeRect(440, 440, 144, 144);

            // Memory Outlines
            ctx.strokeRect(710, 360, 120, 150);
            ctx.strokeRect(710, 540, 120, 150);

            // GPIO Header Outline
            ctx.strokeRect(580, 150, 260, 60);

            // Corner Clearances
            ctx.beginPath();
            ctx.arc(90, 90, 32, 0, Math.PI * 2);
            ctx.arc(934, 90, 32, 0, Math.PI * 2);
            ctx.arc(90, 934, 32, 0, Math.PI * 2);
            ctx.arc(934, 934, 32, 0, Math.PI * 2);
            ctx.stroke();

            // Silkscreen Typography
            ctx.font = 'bold 20px monospace';
            ctx.fillText('ELECTRODESK SBC-V2', 120, 140);
            ctx.font = '14px monospace';
            ctx.fillText('REV 2.4 // 64-BIT ARM', 120, 168);
            ctx.fillText('U1 SoC', 480, 430);
            ctx.fillText('U2 DRAM', 730, 350);
            ctx.fillText('U3 FLASH', 730, 715);
            ctx.fillText('USB 3.0', 100, 780);
            ctx.fillText('GbE LAN', 100, 310);
            ctx.fillText('GPIO 40-PIN', 640, 140);
            ctx.fillText('PIN 1', 580, 140);

            // Cyan Cyber Accents in Silkscreen
            ctx.strokeStyle = '#22d3ee';
            ctx.lineWidth = 2;
            ctx.strokeRect(432, 432, 160, 160);

            const texture = new THREE.CanvasTexture(texCanvas);
            texture.generateMipmaps = true;
            texture.minFilter = THREE.LinearMipmapLinearFilter;
            return texture;
        }

        const pcbTexture = generateProceduralPcbTexture();

        // 6. PBR Material Library
        const materials = {
            standoffBlack: new THREE.MeshStandardMaterial({
                color: 0x18181b,
                metalness: 0.78,
                roughness: 0.35
            }),
            basePlate: new THREE.MeshStandardMaterial({
                color: 0xd8dee9,
                metalness: 0.12,
                roughness: 0.65
            }),
            copperTrace: new THREE.MeshStandardMaterial({
                color: 0xe08238,
                metalness: 0.95,
                roughness: 0.20
            }),
            goldPad: new THREE.MeshStandardMaterial({
                color: 0xf59e0b,
                metalness: 0.98,
                roughness: 0.18
            }),
            pcbGreenClearcoat: new THREE.MeshPhysicalMaterial({
                map: pcbTexture,
                color: 0xffffff,
                roughness: 0.32,
                metalness: 0.15,
                clearcoat: 0.75,
                clearcoatRoughness: 0.12
            }),
            chipMatte: new THREE.MeshStandardMaterial({
                color: 0x18181b,
                metalness: 0.18,
                roughness: 0.75
            }),
            chipHeatSpreader: new THREE.MeshStandardMaterial({
                color: 0x94a3b8,
                metalness: 0.88,
                roughness: 0.22
            }),
            heatsinkAluminum: new THREE.MeshStandardMaterial({
                color: 0xd1d5db,
                metalness: 0.92,
                roughness: 0.24
            }),
            portBrushedMetal: new THREE.MeshStandardMaterial({
                color: 0xe2e8f0,
                metalness: 0.94,
                roughness: 0.22
            }),
            portTongueBlue: new THREE.MeshStandardMaterial({
                color: 0x0284c7,
                roughness: 0.45
            }),
            pinGold: new THREE.MeshStandardMaterial({
                color: 0xf59e0b,
                metalness: 0.98,
                roughness: 0.18
            }),
            headerBaseBlack: new THREE.MeshStandardMaterial({
                color: 0x18181b,
                roughness: 0.85
            }),
            smdResistor: new THREE.MeshStandardMaterial({
                color: 0x262626,
                metalness: 0.5,
                roughness: 0.4
            }),
            smdCapacitor: new THREE.MeshStandardMaterial({
                color: 0x854d0e,
                metalness: 0.65,
                roughness: 0.3
            }),
            screwSteel: new THREE.MeshStandardMaterial({
                color: 0xcfd8dc,
                metalness: 0.95,
                roughness: 0.15
            }),
            ledCyan: new THREE.MeshStandardMaterial({
                color: 0x22d3ee,
                emissive: 0x22d3ee,
                emissiveIntensity: 1.2,
                roughness: 0.2
            }),
            ledAmber: new THREE.MeshStandardMaterial({
                color: 0xfbbf24,
                emissive: 0xd97706,
                emissiveIntensity: 0.8,
                roughness: 0.2
            }),
            ledGreen: new THREE.MeshStandardMaterial({
                color: 0x10b981,
                emissive: 0x059669,
                emissiveIntensity: 0.9,
                roughness: 0.2
            })
        };

        const pulsingLeds = [materials.ledCyan];

        // 7. Root Board Group
        const boardRoot = new THREE.Group();
        boardRoot.rotation.x = 0.22;
        boardRoot.rotation.y = -0.48;
        scene.add(boardRoot);

        // Staggered Layer System for Bottom-to-Top Animation
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

        // --- LAYER 1 (Bottom): 4 Black Standoff Feet ---
        const standoffsGroup = new THREE.Group();
        cornerPositions.forEach(pos => {
            const foot = new THREE.Mesh(
                new THREE.CylinderGeometry(0.14, 0.14, 0.32, 20),
                materials.standoffBlack
            );
            foot.position.set(pos.x, 0, pos.z);
            foot.castShadow = true;
            foot.receiveShadow = true;
            standoffsGroup.add(foot);
        });
        addLayer(standoffsGroup, -1.8, -0.16, 0.00, 0.50);

        // --- LAYER 2: Pale Base Sheet ---
        const baseSheetGroup = new THREE.Group();
        const baseSheet = new THREE.Mesh(
            new THREE.BoxGeometry(4.2, 0.04, 2.8),
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
            new THREE.BoxGeometry(1.2, 0.015, 1.2),
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

        // --- LAYER 4: Green Solder-Mask PCB with Clearcoat ---
        const pcbGroup = new THREE.Group();
        const pcbBoard = new THREE.Mesh(
            new THREE.BoxGeometry(4.2, 0.06, 2.8),
            materials.pcbGreenClearcoat
        );
        pcbBoard.castShadow = true;
        pcbBoard.receiveShadow = true;
        pcbGroup.add(pcbBoard);
        addLayer(pcbGroup, 1.4, 0.06, 0.26, 0.80);

        // --- LAYER 5: InstancedMesh for 48 SMD Components ---
        const smdCount = 48;
        const smdGeo = new THREE.BoxGeometry(0.12, 0.05, 0.07);
        const smdInstanced = new THREE.InstancedMesh(smdGeo, materials.smdCapacitor, smdCount);
        smdInstanced.castShadow = true;
        smdInstanced.receiveShadow = true;

        const dummy = new THREE.Object3D();
        let idx = 0;

        // Decoupling array around CPU
        for (let x = -0.7; x <= 0.7; x += 0.28) {
            dummy.position.set(x, 0.09, -0.65);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);

            dummy.position.set(x, 0.09, 0.65);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);
        }

        // Filtering capacitors around RAM
        for (let z = -0.7; z <= 0.7; z += 0.22) {
            dummy.position.set(1.25, 0.09, z);
            dummy.rotation.y = Math.PI / 2;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);
        }

        // Power rail SMD bank near USB/Ethernet
        for (let z = -0.2; z <= 0.5; z += 0.18) {
            dummy.position.set(-1.1, 0.09, z);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);

            dummy.position.set(-0.95, 0.09, z);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);
        }

        // Fill remaining instances across board
        while (idx < smdCount) {
            dummy.position.set(-0.4 + (idx % 4) * 0.2, 0.09, -0.85);
            dummy.rotation.y = 0;
            dummy.updateMatrix();
            smdInstanced.setMatrixAt(idx++, dummy.matrix);
        }
        smdInstanced.instanceMatrix.needsUpdate = true;

        const smdGroup = new THREE.Group();
        smdGroup.add(smdInstanced);
        addLayer(smdGroup, 2.5, 0.03, 0.34, 0.86);

        // --- LAYER 6: IC Chips, Stacked Ports & Pin Header ---
        const compGroup = new THREE.Group();

        // Central SoC Processor
        const cpuPkg = new THREE.Mesh(new THREE.BoxGeometry(1.02, 0.10, 1.02), materials.chipMatte);
        cpuPkg.castShadow = true;
        cpuPkg.receiveShadow = true;
        compGroup.add(cpuPkg);

        const cpuSpreader = new THREE.Mesh(new THREE.BoxGeometry(0.86, 0.03, 0.86), materials.chipHeatSpreader);
        cpuSpreader.position.set(0, 0.055, 0);
        cpuSpreader.castShadow = true;
        compGroup.add(cpuSpreader);

        const cpuStatusLed = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.04, 0.08), materials.ledCyan);
        cpuStatusLed.position.set(0.34, 0.065, 0.34);
        compGroup.add(cpuStatusLed);

        // RAM Chips (2 Units)
        [-0.42, 0.42].forEach(z => {
            const ram = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.08, 0.74), materials.chipMatte);
            ram.position.set(0.85, 0, z);
            ram.castShadow = true;
            compGroup.add(ram);
        });

        // Stacked Dual USB 3.0 Type-A Metal Block
        const usbBlock = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.54, 0.76), materials.portBrushedMetal);
        usbBlock.castShadow = true;
        usbBlock.receiveShadow = true;

        [-0.13, 0.13].forEach(yOff => {
            const tongue = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.05, 0.28), materials.portTongueBlue);
            tongue.position.set(-0.35, yOff, 0);
            usbBlock.add(tongue);
        });
        usbBlock.position.set(-1.62, 0.20, 0.85);
        compGroup.add(usbBlock);

        // RJ-45 Gigabit Ethernet Metal Block with Status LEDs
        const ethBlock = new THREE.Mesh(new THREE.BoxGeometry(0.74, 0.58, 0.82), materials.portBrushedMetal);
        ethBlock.castShadow = true;
        ethBlock.receiveShadow = true;

        const ethLed1 = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.06, 0.06), materials.ledCyan);
        ethLed1.position.set(-0.37, 0.24, -0.22);
        ethBlock.add(ethLed1);
        const ethLed2 = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.06, 0.06), materials.ledAmber);
        ethLed2.position.set(-0.37, 0.24, 0.22);
        ethBlock.add(ethLed2);

        ethBlock.position.set(-1.62, 0.22, -0.55);
        compGroup.add(ethBlock);

        // HDMI Output Port
        const hdmiPort = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.22, 0.38), materials.portBrushedMetal);
        hdmiPort.position.set(0.35, 0.06, -1.25);
        hdmiPort.castShadow = true;
        compGroup.add(hdmiPort);

        // 40-Pin GPIO Header Strip (Dual-row gold pins on black insulator)
        const gpioBase = new THREE.Mesh(new THREE.BoxGeometry(1.68, 0.12, 0.24), materials.headerBaseBlack);
        gpioBase.position.set(0.65, 0.06, 1.15);
        gpioBase.castShadow = true;
        compGroup.add(gpioBase);

        for (let x = -0.72; x <= 0.72; x += 0.18) {
            [-0.06, 0.06].forEach(z => {
                const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.024, 0.024, 0.38, 8), materials.pinGold);
                pin.position.set(0.65 + x, 0.25, 1.15 + z);
                pin.castShadow = true;
                compGroup.add(pin);
            });
        }

        addLayer(compGroup, 2.9, 0.14, 0.40, 0.92);

        // --- LAYER 7: Extruded Finned Aluminum Heatsink ---
        const heatsinkGroup = new THREE.Group();
        const hsBase = new THREE.Mesh(new THREE.BoxGeometry(1.08, 0.08, 1.08), materials.heatsinkAluminum);
        hsBase.castShadow = true;
        hsBase.receiveShadow = true;
        heatsinkGroup.add(hsBase);

        // 6 Vertical extruded cooling fins
        for (let f = -0.42; f <= 0.42; f += 0.168) {
            const fin = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.36, 1.06), materials.heatsinkAluminum);
            fin.position.set(f, 0.21, 0);
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

        // 8. Animation State & Timing
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

        // Mouse Parallax Handling
        const mouseTarget = { x: 0, y: 0 };
        const mouseCurrent = { x: 0, y: 0 };

        function onMouseMove(e) {
            const nx = (e.clientX / window.innerWidth) - 0.5;
            const ny = (e.clientY / window.innerHeight) - 0.5;
            mouseTarget.x = nx * 0.35;
            mouseTarget.y = ny * 0.25;
        }
        window.addEventListener('mousemove', onMouseMove, { passive: true });

        // Responsive Resizing
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

        // Pause Rendering When Tab Is Hidden (Performance)
        document.addEventListener('visibilitychange', () => {
            isRunning = !document.hidden;
            if (isRunning) requestAnimationFrame(renderLoop);
        });

        // Main Render Loop
        function renderLoop(now) {
            if (!isRunning) return;

            // Dynamically detect container resize
            if (container && container.clientWidth > 0 && container.clientHeight > 0) {
                if (Math.abs(container.clientWidth - width) > 8 || Math.abs(container.clientHeight - height) > 8) {
                    onWindowResize();
                }
            }

            const elapsed = now - startTime;

            // Step 1: Bottom-to-Top Staggered Assembly
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

            // Step 2 & 3: Post-Assembly Power-On Pulse & Idle Motion
            if (isAssembled) {
                const idleTime = (now - assemblyFinishTime) * 0.001;

                // Power-On Cyan Pulse along traces right after assembly
                if (idleTime < 1.6) {
                    const pulseT = idleTime / 1.6;
                    powerPulseLight.intensity = Math.sin(pulseT * Math.PI) * 3.5;
                    materials.ledCyan.emissiveIntensity = 1.0 + Math.sin(pulseT * Math.PI * 4) * 2.5;
                    materials.ledAmber.emissiveIntensity = 0.5 + Math.cos(pulseT * Math.PI * 4) * 1.5;
                    if (statusText && idleTime > 0.8) {
                        statusText.textContent = 'ELECTRODESK SBC ONLINE // ALL SYSTEMS NOMINAL';
                    }
                } else if (!isPoweringOn) {
                    // Regular gentle pulse
                    const pulse = 0.75 + 0.55 * Math.sin(idleTime * 3.2);
                    pulsingLeds.forEach(mat => {
                        mat.emissiveIntensity = pulse;
                    });
                    powerPulseLight.intensity = 0.5 + 0.45 * Math.sin(idleTime * 3.2);
                }

                // Smooth idle floating & gentle sway
                boardRoot.position.y = Math.sin(idleTime * 1.15) * 0.08;

                mouseCurrent.x += (mouseTarget.x - mouseCurrent.x) * 0.045;
                mouseCurrent.y += (mouseTarget.y - mouseCurrent.y) * 0.045;

                boardRoot.rotation.y = -0.48 + Math.sin(idleTime * 0.32) * 0.06 + mouseCurrent.x;
                boardRoot.rotation.x =  0.22 + Math.cos(idleTime * 0.42) * 0.03 + mouseCurrent.y;
            }

            renderer.render(scene, camera);
            requestAnimationFrame(renderLoop);
        }

        requestAnimationFrame(renderLoop);

        // 9. Login Submit Power-On Flash
        window.triggerBoardPowerOn = function (callback) {
            if (isPoweringOn) {
                if (callback) callback();
                return;
            }
            isPoweringOn = true;

            if (statusText) statusText.textContent = 'SYSTEM POWERING ON...';

            const overlay = document.getElementById('login-poweron-overlay');
            if (overlay) overlay.classList.add('login-poweron-active');

            pulsingLeds.forEach(mat => {
                mat.emissiveIntensity = 5.0;
                mat.emissive.setHex(0x38bdf8);
            });
            powerPulseLight.intensity = 5.8;
            powerPulseLight.color.setHex(0x38bdf8);

            camera.position.z -= 0.35;
            camera.position.y += 0.15;

            setTimeout(() => {
                if (callback) callback();
            }, 440);
        };

        // 10. Disposal on Unload (Performance)
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

            if (pcbTexture) pcbTexture.dispose();

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
