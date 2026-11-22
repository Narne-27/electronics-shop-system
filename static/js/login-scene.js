/**
 * Electrodesk - 3D Exploded Circuit Board Intro Scene
 * Built strictly with Three.js BoxGeometry & CylinderGeometry.
 * Scoped exclusively to the /login page.
 */

(function () {
    'use strict';

    let sceneInitialized = false;

    function initScene() {
        if (sceneInitialized) return;

        if (typeof THREE === 'undefined') {
            // Retry if Three.js is still loading asynchronously
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

        sceneInitialized = true;

        // Check user preference for reduced motion
        const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        // Determine dimensions safely (minimum 320x300)
        let width = Math.max(container.clientWidth || 0, 360);
        let height = Math.max(container.clientHeight || 0, 340);

        // Scene, Camera, Renderer
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
        camera.position.set(5.2, 4.5, 5.6);
        camera.lookAt(0, 0.4, 0);

        const renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            alpha: true,
            antialias: true,
            powerPreference: 'high-performance'
        });
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setClearColor(0x000000, 0); // 100% transparent for background particles

        // Lighting Setup
        const ambientLight = new THREE.AmbientLight(0xffffff, 1.4);
        scene.add(ambientLight);

        // Key Light (White Directional)
        const keyLight = new THREE.DirectionalLight(0xffffff, 2.0);
        keyLight.position.set(6, 10, 6);
        scene.add(keyLight);

        // Cyan Rim Light
        const cyanRimLight = new THREE.DirectionalLight(0x22d3ee, 2.2);
        cyanRimLight.position.set(-6, 4, -4);
        scene.add(cyanRimLight);

        // Warm Copper Accent Light
        const copperFill = new THREE.PointLight(0xf59e0b, 1.2, 14);
        copperFill.position.set(2, -2, 2);
        scene.add(copperFill);

        // Cyan Chip Status Light
        const powerLight = new THREE.PointLight(0x22d3ee, 1.0, 10);
        powerLight.position.set(0, 0.8, 0);
        scene.add(powerLight);

        // Material Library
        const materials = {
            standoff: new THREE.MeshStandardMaterial({
                color: 0xd97706,
                metalness: 0.88,
                roughness: 0.28
            }),
            basePlate: new THREE.MeshStandardMaterial({
                color: 0xcfd8dc,
                metalness: 0.10,
                roughness: 0.65
            }),
            copperTrace: new THREE.MeshStandardMaterial({
                color: 0xe08d3c,
                metalness: 0.95,
                roughness: 0.22
            }),
            goldPad: new THREE.MeshStandardMaterial({
                color: 0xf59e0b,
                metalness: 0.92,
                roughness: 0.25
            }),
            pcbGreen: new THREE.MeshStandardMaterial({
                color: 0x065f46,
                metalness: 0.25,
                roughness: 0.38
            }),
            silkscreenWhite: new THREE.MeshStandardMaterial({
                color: 0xe2e8f0,
                roughness: 0.6
            }),
            silkscreenCyan: new THREE.MeshStandardMaterial({
                color: 0x22d3ee,
                emissive: 0x0891b2,
                emissiveIntensity: 0.45,
                roughness: 0.35
            }),
            chipPackage: new THREE.MeshStandardMaterial({
                color: 0x18181b,
                metalness: 0.2,
                roughness: 0.75
            }),
            chipHeatSpreader: new THREE.MeshStandardMaterial({
                color: 0x94a3b8,
                metalness: 0.85,
                roughness: 0.22
            }),
            chipCyanGlow: new THREE.MeshStandardMaterial({
                color: 0x22d3ee,
                emissive: 0x22d3ee,
                emissiveIntensity: 1.2,
                roughness: 0.2
            }),
            chipAmberLed: new THREE.MeshStandardMaterial({
                color: 0xfbbf24,
                emissive: 0xd97706,
                emissiveIntensity: 0.8,
                roughness: 0.2
            }),
            metalPort: new THREE.MeshStandardMaterial({
                color: 0xe2e8f0,
                metalness: 0.92,
                roughness: 0.18
            }),
            portTongue: new THREE.MeshStandardMaterial({
                color: 0x0284c7,
                roughness: 0.5
            }),
            pinGold: new THREE.MeshStandardMaterial({
                color: 0xf59e0b,
                metalness: 0.95,
                roughness: 0.2
            }),
            headerBase: new THREE.MeshStandardMaterial({
                color: 0x1e293b,
                roughness: 0.8
            }),
            inductorCore: new THREE.MeshStandardMaterial({
                color: 0x334155,
                metalness: 0.4,
                roughness: 0.7
            }),
            smdCapacitor: new THREE.MeshStandardMaterial({
                color: 0xb45309,
                metalness: 0.5,
                roughness: 0.4
            }),
            screwSteel: new THREE.MeshStandardMaterial({
                color: 0xcfd8dc,
                metalness: 0.94,
                roughness: 0.15
            }),
            shadowFloor: new THREE.MeshBasicMaterial({
                color: 0x020617,
                transparent: true,
                opacity: 0.42
            })
        };

        const pulsingEmissives = [materials.chipCyanGlow, materials.silkscreenCyan];

        // Board Root Assembly Group
        const boardRoot = new THREE.Group();
        boardRoot.rotation.x = 0.24;
        boardRoot.rotation.y = -0.52;
        scene.add(boardRoot);

        const animatedParts = [];

        function registerAnimatedPart(obj, explodedY, assembledY, options = {}) {
            obj.position.y = prefersReducedMotion ? assembledY : explodedY;
            boardRoot.add(obj);
            animatedParts.push({
                obj: obj,
                explodedY: explodedY,
                assembledY: assembledY,
                rotatesY: options.rotatesY || false,
                initialRotY: obj.rotation.y,
                screwTurns: options.screwTurns || 0
            });
            return obj;
        }

        // 1. LAYER 1: 4 Standoff Feet & Ground Shadow
        const standoffsGroup = new THREE.Group();
        const cornerPositions = [
            { x: -1.85, z: -1.22 },
            { x:  1.85, z: -1.22 },
            { x: -1.85, z:  1.22 },
            { x:  1.85, z:  1.22 }
        ];

        cornerPositions.forEach(pos => {
            const foot = new THREE.Mesh(
                new THREE.CylinderGeometry(0.12, 0.14, 0.30, 16),
                materials.standoff
            );
            foot.position.set(pos.x, 0, pos.z);
            standoffsGroup.add(foot);
        });

        registerAnimatedPart(standoffsGroup, -1.8, -0.15);

        // Soft Shadow Mesh under the board
        const shadowMesh = new THREE.Mesh(
            new THREE.CylinderGeometry(2.5, 2.7, 0.01, 32),
            materials.shadowFloor
        );
        shadowMesh.position.set(0, -0.32, 0);
        boardRoot.add(shadowMesh);

        // 2. LAYER 2: Pale Base Substrate Sheet
        const baseSheetGroup = new THREE.Group();
        const basePlate = new THREE.Mesh(
            new THREE.BoxGeometry(4.2, 0.04, 2.8),
            materials.basePlate
        );
        baseSheetGroup.add(basePlate);

        cornerPositions.forEach(pos => {
            const ring = new THREE.Mesh(
                new THREE.CylinderGeometry(0.20, 0.20, 0.045, 16),
                materials.copperTrace
            );
            ring.position.set(pos.x, 0, pos.z);
            baseSheetGroup.add(ring);
        });

        registerAnimatedPart(baseSheetGroup, -0.95, -0.02);

        // 3. LAYER 3: Copper Trace Layer
        const copperLayerGroup = new THREE.Group();
        const socCopperPad = new THREE.Mesh(
            new THREE.BoxGeometry(1.2, 0.015, 1.2),
            materials.copperTrace
        );
        socCopperPad.position.set(0, 0, 0);
        copperLayerGroup.add(socCopperPad);

        const traceTracks = [
            { x: 0.5, z: -0.4, w: 1.4, d: 0.04 },
            { x: 0.5, z: -0.2, w: 1.2, d: 0.03 },
            { x: 0.5, z:  0.2, w: 1.2, d: 0.03 },
            { x: 0.5, z:  0.4, w: 1.4, d: 0.04 },
            { x: -0.8, z: 0.0, w: 0.04, d: 1.6 },
            { x: -0.9, z: 0.2, w: 0.03, d: 1.4 },
            { x: -1.0, z: -0.3, w: 0.03, d: 1.2 },
            { x: -1.6, z:  0.85, w: 0.7, d: 0.8 },
            { x: -1.6, z: -0.55, w: 0.7, d: 0.8 },
            { x:  0.6, z:  1.15, w: 1.7, d: 0.25 }
        ];

        traceTracks.forEach(t => {
            const tr = new THREE.Mesh(
                new THREE.BoxGeometry(t.w, 0.014, t.d),
                materials.copperTrace
            );
            tr.position.set(t.x, 0, t.z);
            copperLayerGroup.add(tr);
        });

        cornerPositions.forEach(pos => {
            const ring = new THREE.Mesh(
                new THREE.CylinderGeometry(0.24, 0.24, 0.016, 16),
                materials.goldPad
            );
            ring.position.set(pos.x, 0, pos.z);
            copperLayerGroup.add(ring);
        });

        registerAnimatedPart(copperLayerGroup, 0.35, 0.02);

        // 4. LAYER 4: Green PCB Solder Mask with Silkscreen
        const pcbGroup = new THREE.Group();
        const pcbBoard = new THREE.Mesh(
            new THREE.BoxGeometry(4.2, 0.06, 2.8),
            materials.pcbGreen
        );
        pcbGroup.add(pcbBoard);

        const silkscreenDetails = [
            { x: 0, z: 0, w: 1.3, d: 0.03, mat: materials.silkscreenWhite },
            { x: 0, z: 0, w: 0.03, d: 1.3, mat: materials.silkscreenWhite },
            { x: 0.85, z: -0.4, w: 0.6, d: 0.8, mat: materials.silkscreenWhite },
            { x: 0.85, z:  0.4, w: 0.6, d: 0.8, mat: materials.silkscreenWhite },
            { x: -0.4, z: -0.85, w: 1.1, d: 0.03, mat: materials.silkscreenCyan },
            { x:  0.7, z: -0.95, w: 0.9, d: 0.03, mat: materials.silkscreenCyan },
            { x: -0.3, z:  0.85, w: 0.8, d: 0.03, mat: materials.silkscreenCyan }
        ];

        silkscreenDetails.forEach(s => {
            const mark = new THREE.Mesh(
                new THREE.BoxGeometry(s.w, 0.065, s.d),
                s.mat
            );
            mark.position.set(s.x, 0.001, s.z);
            pcbGroup.add(mark);
        });

        registerAnimatedPart(pcbGroup, 1.4, 0.06);

        // 5. LAYER 5: Electronic Components
        // Central SoC / CPU Processor
        const cpuGroup = new THREE.Group();
        const cpuPackage = new THREE.Mesh(
            new THREE.BoxGeometry(1.0, 0.10, 1.0),
            materials.chipPackage
        );
        cpuGroup.add(cpuPackage);

        const cpuHeatSpreader = new THREE.Mesh(
            new THREE.BoxGeometry(0.82, 0.03, 0.82),
            materials.chipHeatSpreader
        );
        cpuHeatSpreader.position.set(0, 0.055, 0);
        cpuGroup.add(cpuHeatSpreader);

        const cpuLed = new THREE.Mesh(
            new THREE.BoxGeometry(0.09, 0.05, 0.09),
            materials.chipCyanGlow
        );
        cpuLed.position.set(0.32, 0.065, 0.32);
        cpuGroup.add(cpuLed);

        for (let i = -0.42; i <= 0.42; i += 0.12) {
            const p1 = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.03, 0.08), materials.goldPad);
            p1.position.set(i, -0.04, -0.52);
            cpuGroup.add(p1);

            const p2 = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.03, 0.08), materials.goldPad);
            p2.position.set(i, -0.04, 0.52);
            cpuGroup.add(p2);

            const p3 = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.03, 0.04), materials.goldPad);
            p3.position.set(-0.52, -0.04, i);
            cpuGroup.add(p3);

            const p4 = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.03, 0.04), materials.goldPad);
            p4.position.set(0.52, -0.04, i);
            cpuGroup.add(p4);
        }

        cpuGroup.position.set(0, 0, 0);
        registerAnimatedPart(cpuGroup, 2.7, 0.14);

        // RAM Memory ICs (2 Units)
        const memoryGroup = new THREE.Group();
        [-0.4, 0.4].forEach(zOffset => {
            const memIc = new THREE.Mesh(
                new THREE.BoxGeometry(0.52, 0.08, 0.72),
                materials.chipPackage
            );
            memIc.position.set(0.85, 0, zOffset);
            memoryGroup.add(memIc);

            const memDot = new THREE.Mesh(
                new THREE.BoxGeometry(0.05, 0.02, 0.05),
                materials.chipCyanGlow
            );
            memDot.position.set(0.85, 0.045, zOffset - 0.22);
            memoryGroup.add(memDot);
        });
        registerAnimatedPart(memoryGroup, 2.9, 0.13);

        // Dual USB Type-A Port Block
        const usbGroup = new THREE.Group();
        const usbMetal = new THREE.Mesh(
            new THREE.BoxGeometry(0.68, 0.52, 0.76),
            materials.metalPort
        );
        usbGroup.add(usbMetal);

        [-0.12, 0.12].forEach(yOff => {
            const tongue = new THREE.Mesh(
                new THREE.BoxGeometry(0.2, 0.05, 0.28),
                materials.portTongue
            );
            tongue.position.set(-0.35, yOff, 0);
            usbGroup.add(tongue);
        });

        usbGroup.position.set(-1.62, 0, 0.85);
        registerAnimatedPart(usbGroup, 3.3, 0.33);

        // RJ-45 Ethernet Jack Block
        const rj45Group = new THREE.Group();
        const rj45Metal = new THREE.Mesh(
            new THREE.BoxGeometry(0.72, 0.55, 0.82),
            materials.metalPort
        );
        rj45Group.add(rj45Metal);

        const ethCyanLed = new THREE.Mesh(
            new THREE.BoxGeometry(0.06, 0.06, 0.06),
            materials.chipCyanGlow
        );
        ethCyanLed.position.set(-0.36, 0.22, -0.22);
        rj45Group.add(ethCyanLed);

        const ethAmberLed = new THREE.Mesh(
            new THREE.BoxGeometry(0.06, 0.06, 0.06),
            materials.chipAmberLed
        );
        ethAmberLed.position.set(-0.36, 0.22, 0.22);
        rj45Group.add(ethAmberLed);

        rj45Group.position.set(-1.62, 0, -0.55);
        registerAnimatedPart(rj45Group, 3.5, 0.35);

        // HDMI Output Port
        const hdmiGroup = new THREE.Group();
        const hdmiMetal = new THREE.Mesh(
            new THREE.BoxGeometry(0.55, 0.22, 0.38),
            materials.metalPort
        );
        hdmiGroup.add(hdmiMetal);
        hdmiGroup.position.set(0.35, 0, -1.25);
        registerAnimatedPart(hdmiGroup, 3.1, 0.18);

        // GPIO Pin Header Strip (2x8 Pins)
        const gpioGroup = new THREE.Group();
        const gpioBase = new THREE.Mesh(
            new THREE.BoxGeometry(1.65, 0.10, 0.24),
            materials.headerBase
        );
        gpioGroup.add(gpioBase);

        for (let x = -0.7; x <= 0.7; x += 0.2) {
            [-0.06, 0.06].forEach(z => {
                const pin = new THREE.Mesh(
                    new THREE.CylinderGeometry(0.024, 0.024, 0.38, 8),
                    materials.pinGold
                );
                pin.position.set(x, 0.18, z);
                gpioGroup.add(pin);
            });
        }

        gpioGroup.position.set(0.65, 0, 1.15);
        registerAnimatedPart(gpioGroup, 3.2, 0.20);

        // SMD Ferrite Inductor & Capacitors
        const smdGroup = new THREE.Group();
        const inductor = new THREE.Mesh(
            new THREE.BoxGeometry(0.42, 0.22, 0.42),
            materials.inductorCore
        );
        inductor.position.set(-0.65, 0, -0.75);
        smdGroup.add(inductor);

        const indStrap = new THREE.Mesh(
            new THREE.BoxGeometry(0.44, 0.08, 0.16),
            materials.copperTrace
        );
        indStrap.position.set(-0.65, 0.04, -0.75);
        smdGroup.add(indStrap);

        const capOffsets = [
            { x: -0.65, z: 0.15 },
            { x: -0.65, z: 0.32 },
            { x: -0.25, z: 0.75 },
            { x: -0.40, z: 0.75 }
        ];

        capOffsets.forEach(pos => {
            const cap = new THREE.Mesh(
                new THREE.BoxGeometry(0.12, 0.08, 0.10),
                materials.smdCapacitor
            );
            cap.position.set(pos.x, 0, pos.z);
            smdGroup.add(cap);
        });

        registerAnimatedPart(smdGroup, 2.6, 0.14);

        // 6. LAYER 6: 4 Corner Screws
        cornerPositions.forEach(pos => {
            const screwGroup = new THREE.Group();

            const screwHead = new THREE.Mesh(
                new THREE.CylinderGeometry(0.14, 0.13, 0.07, 16),
                materials.screwSteel
            );
            screwHead.position.set(0, 0.035, 0);
            screwGroup.add(screwHead);

            const slot1 = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.02, 0.04), materials.chipPackage);
            slot1.position.set(0, 0.075, 0);
            screwGroup.add(slot1);
            const slot2 = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.02, 0.18), materials.chipPackage);
            slot2.position.set(0, 0.075, 0);
            screwGroup.add(slot2);

            const shank = new THREE.Mesh(
                new THREE.CylinderGeometry(0.05, 0.05, 0.28, 8),
                materials.screwSteel
            );
            shank.position.set(0, -0.12, 0);
            screwGroup.add(shank);

            screwGroup.position.set(pos.x, 0, pos.z);
            registerAnimatedPart(screwGroup, 4.3, 0.13, {
                rotatesY: true,
                screwTurns: 6.0
            });
        });

        // Timing & Animation Variables
        const START_DELAY_MS = 800;
        const ANIM_DURATION_MS = 3000;
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

            // Check if container dynamically resized
            if (container && container.clientWidth > 0 && container.clientHeight > 0) {
                if (Math.abs(container.clientWidth - width) > 10 || Math.abs(container.clientHeight - height) > 10) {
                    onWindowResize();
                }
            }

            const elapsed = now - startTime;

            if (!prefersReducedMotion) {
                if (elapsed < START_DELAY_MS) {
                    if (statusText) statusText.textContent = 'EXPLODED VIEW // STANDBY';
                } else if (elapsed < START_DELAY_MS + ANIM_DURATION_MS) {
                    const rawProgress = (elapsed - START_DELAY_MS) / ANIM_DURATION_MS;
                    const progress = easeInOutCubic(Math.min(Math.max(rawProgress, 0), 1));

                    animatedParts.forEach(p => {
                        p.obj.position.y = p.explodedY + (p.assembledY - p.explodedY) * progress;
                        if (p.rotatesY) {
                            p.obj.rotation.y = p.initialRotY + (p.screwTurns * Math.PI * 2 * progress);
                        }
                    });

                    if (statusText) statusText.textContent = 'ASSEMBLING CIRCUIT BOARD...';
                } else if (!isAssembled) {
                    isAssembled = true;
                    assemblyFinishTime = now;
                    animatedParts.forEach(p => {
                        p.obj.position.y = p.assembledY;
                        if (p.rotatesY) {
                            p.obj.rotation.y = p.initialRotY + (p.screwTurns * Math.PI * 2);
                        }
                    });
                    if (statusText) statusText.textContent = 'ELECTRODESK HARDWARE ASSEMBLED';
                }
            }

            if (isAssembled) {
                const idleTime = (now - assemblyFinishTime) * 0.001;

                boardRoot.position.y = Math.sin(idleTime * 1.15) * 0.08;

                mouseCurrent.x += (mouseTarget.x - mouseCurrent.x) * 0.045;
                mouseCurrent.y += (mouseTarget.y - mouseCurrent.y) * 0.045;

                boardRoot.rotation.y = -0.52 + Math.sin(idleTime * 0.35) * 0.07 + mouseCurrent.x;
                boardRoot.rotation.x =  0.24 + Math.cos(idleTime * 0.45) * 0.04 + mouseCurrent.y;

                if (!isPoweringOn) {
                    const pulseIntensity = 0.75 + 0.65 * Math.sin(idleTime * 3.4);
                    pulsingEmissives.forEach(mat => {
                        mat.emissiveIntensity = pulseIntensity;
                    });
                    powerLight.intensity = 0.6 + 0.55 * Math.sin(idleTime * 3.4);
                }
            }

            renderer.render(scene, camera);
            requestAnimationFrame(renderLoop);
        }

        requestAnimationFrame(renderLoop);

        // Power-On Effect on Login Submit
        window.triggerBoardPowerOn = function (callback) {
            if (isPoweringOn) {
                if (callback) callback();
                return;
            }
            isPoweringOn = true;

            if (statusText) statusText.textContent = 'SYSTEM POWERING ON...';

            const overlay = document.getElementById('login-poweron-overlay');
            if (overlay) overlay.classList.add('login-poweron-active');

            pulsingEmissives.forEach(mat => {
                mat.emissiveIntensity = 5.0;
                mat.emissive.setHex(0x38bdf8);
            });
            powerLight.intensity = 5.5;
            powerLight.color.setHex(0x38bdf8);

            camera.position.z -= 0.35;
            camera.position.y += 0.15;

            setTimeout(() => {
                if (callback) callback();
            }, 440);
        };

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

            if (renderer) {
                renderer.dispose();
                renderer.forceContextLoss();
            }
        }

        window.addEventListener('beforeunload', disposeScene);
    }

    // Expose for explicit invocation or module fallback
    window.initLoginScene = initScene;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initScene);
    } else {
        initScene();
    }
    window.addEventListener('load', initScene);
})();
