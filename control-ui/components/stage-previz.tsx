import React, { useState, useEffect, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Box, Cylinder, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import { XR, Controllers, Hands, VRButton, useXR, Interactive } from '@react-three/xr';

interface StagePrevizProps {
  webRtcStreamUrl?: string;
  width?: number;
  height?: number;
}

// A simple projector cone
function ProjectorCone({ position, rotation, color = "#ffffff", opacity = 0.3 }: any) {
  return (
    <group position={position} rotation={rotation}>
      <Cylinder args={[0.01, 2, 8, 32, 1, true]} position={[0, -4, 0]}>
        <meshBasicMaterial color={color} transparent opacity={opacity} side={THREE.DoubleSide} depthWrite={false} blending={THREE.AdditiveBlending} />
      </Cylinder>
    </group>
  );
}

// The main screen that receives the video texture
function StageScreen({ videoTexture }: { videoTexture: THREE.VideoTexture | null }) {
  return (
    <Box args={[16, 9, 0.5]} position={[0, 4.5, -5]}>
      <meshStandardMaterial 
        color={videoTexture ? "#ffffff" : "#111111"} 
        map={videoTexture || null}
        emissive={videoTexture ? "#ffffff" : "#000000"}
        emissiveMap={videoTexture || null}
        emissiveIntensity={0.8}
      />
    </Box>
  );
}

// The floor of the stage
function StageFloor() {
  return (
    <Box args={[20, 0.5, 10]} position={[0, -0.25, 0]}>
      <meshStandardMaterial color="#333" roughness={0.8} metalness={0.2} />
      <gridHelper args={[20, 20, "#555", "#222"]} position={[0, 0.26, 0]} />
    </Box>
  );
}

function VROperatorControls() {
  const { isPresenting } = useXR();
  
  const handleSelect = () => {
    if (isPresenting) {
      console.log("[VR] Controller Triggered: Firing Next Cue");
      // In a real app, this would call triggerEvent({type: "NEXT_CUE"})
    }
  };

  return (
    <Interactive onSelect={handleSelect}>
      <mesh position={[0, 1, 0]} visible={false}>
        <boxGeometry args={[100, 100, 100]} />
      </mesh>
    </Interactive>
  );
}

export function StagePreviz({ webRtcStreamUrl, width = 800, height = 450 }: StagePrevizProps) {
  const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null);
  
  useEffect(() => {
    if (!webRtcStreamUrl) return;
    const video = document.createElement('video');
    video.crossOrigin = 'anonymous';
    video.loop = true;
    video.muted = true;
    video.playsInline = true;
    if (webRtcStreamUrl.startsWith('http') || webRtcStreamUrl.startsWith('blob')) {
      video.src = webRtcStreamUrl;
      video.play().catch(e => console.error("Video play failed", e));
    }
    setVideoElement(video);
    return () => {
      video.pause();
      video.removeAttribute('src');
      video.load();
    };
  }, [webRtcStreamUrl]);

  const videoTexture = useMemo(() => {
    if (!videoElement) return null;
    const texture = new THREE.VideoTexture(videoElement);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }, [videoElement]);

  return (
    <div style={{ position: 'relative', width, height, background: '#000', borderRadius: '8px', overflow: 'hidden', border: '1px solid #333' }}>
      <VRButton />
      <Canvas shadows>
        <XR>
          <PerspectiveCamera makeDefault position={[0, 8, 15]} fov={50} />
          <OrbitControls target={[0, 4, 0]} maxPolarAngle={Math.PI / 2 + 0.1} />
          
          <ambientLight intensity={0.5} />
          <spotLight position={[0, 15, 10]} angle={0.3} penumbra={1} intensity={2} castShadow />
          
          <Controllers />
          <Hands />
          <VROperatorControls />
          
          <StageScreen videoTexture={videoTexture} />
          <StageFloor />
          
          <ProjectorCone position={[-6, 10, 12]} rotation={[Math.PI / 8, -Math.PI / 8, 0]} color="#00ffaa" opacity={0.15} />
          <ProjectorCone position={[6, 10, 12]} rotation={[Math.PI / 8, Math.PI / 8, 0]} color="#ff00aa" opacity={0.15} />
        </XR>
      </Canvas>
    </div>
  );
}
