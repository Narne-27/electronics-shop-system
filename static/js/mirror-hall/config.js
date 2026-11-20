/**
 * Electrodesk - Mirror Hall 3D Section Carousel
 * Configuration Constants & Motion Tunables
 */

export const CONFIG = {
  // Ring Geometry & Dimensions
  cardWidth: 2.2,
  cardHeight: 3.55,           // Aspect ≈ 0.62:1
  cardRadius: 0.15,            // Rounded corner radius
  cardTilt: 0.08,             // Inward tilt in radians
  cardEmissiveBase: 0.25,     // Ambient card edge emissive intensity
  cardEmissiveFocus: 0.95,    // Active/focused card edge glow
  ringRadiusFactor: 1.15,     // Multiplier for auto-computed circle radius

  // Camera & Perspective
  cameraFov: 42,
  cameraY: 1.25,              // Eye level slightly above pool surface
  cameraZ: 8.2,               // Distance from ring center
  lookAtY: 0.55,              // Look target slightly above water line
  parallaxMax: 0.15,          // Pointer parallax shift limit
  parallaxDamping: 0.05,

  // Water Surface & Reflection Pool
  poolWidth: 32,
  poolHeight: 32,
  poolColor: 0x04010a,
  reflectionOpacityBase: 0.38,// Reflection brightness right at card base
  reflectionHeightFade: 0.60, // Reflection falls to 0 by 60% card height
  rippleSpeed: 1.1,
  rippleAmplitude: 0.05,
  rippleVelocityFactor: 1.8,  // Amplitude surge during fast dragging
  lightPoolRadius: 2.8,       // Radial spotlight on pool under centered card

  // Inertia Physics & Spring Snapping
  inertiaDamping: 0.94,       // Per-frame velocity decay (frame-rate normalized)
  velocityClamp: 1.8,         // Max angular rotation speed (rad/s)
  snapThreshold: 0.007,       // Velocity below which spring snap engages
  springK: 16.0,              // Critically damped spring tension
  springDamping: 7.5,
  dragSensitivity: 0.0035,    // Pointer movement to radians
  wheelSensitivity: 0.0018,   // Scroll wheel to radians
  clickDragThreshold: 6,      // Pixels: movement below this is treated as a click

  // Atmosphere & Lighting
  bobAmplitude: 0.02,         // Idle floating bob amplitude
  bobFrequency: 1.3,
  breathAmplitude: 0.15,      // Idle emissive pulse
  fogNear: 6.0,
  fogFar: 18.0,
  fogColor: 0x060212,

  // Procedural Texture Canvas
  textureWidth: 512,
  textureHeight: 825,

  // Performance & Quality Caps
  maxDprDesktop: 2.0,
  maxDprMobile: 1.5,
  fpsDegradeThresholdMs: 22,  // Auto-degrade if avg frame time > 22ms (~45fps)
  mobileBreakpoint: 768
};
