import React from 'react';
import { MobileCuePanel } from '../../components/mobile-cue-panel';
import type { Metadata, Viewport } from 'next';

export const metadata: Metadata = {
  title: 'Cue Panel · StageCanvas',
  description: 'One-touch cue trigger panel for show-day operation',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    title: 'StageCanvas Cue',
    statusBarStyle: 'black-translucent',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover',
  themeColor: '#0a0a1a',
};

export default function MobilePage() {
  return <MobileCuePanel />;
}
