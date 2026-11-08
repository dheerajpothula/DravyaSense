/**
 * BotanicalIllustration
 *
 * Hand-crafted inline SVG combining:
 * - Botanical leaf / herb motifs (referencing herbal Dravya research)
 * - Abstract sensor waveform / scatter-plot nodes (referencing e-tongue data)
 * - Minimal scientific grid lines
 *
 * Uses the DravyaSense brand palette only.
 * No external assets, no dependencies.
 */
export default function BotanicalIllustration({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 560 600"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* ── Background frame ─────────────────────────────────── */}
      <rect width="560" height="600" rx="2" fill="#EEF1EB" />

      {/* ── Subtle grid ──────────────────────────────────────── */}
      {[80, 160, 240, 320, 400, 480].map((y) => (
        <line key={`h${y}`} x1="40" y1={y} x2="520" y2={y}
              stroke="#D2DCDB" strokeWidth="0.5" />
      ))}
      {[80, 160, 240, 320, 400, 480].map((x) => (
        <line key={`v${x}`} x1={x} y1="40" x2={x} y2="560"
              stroke="#D2DCDB" strokeWidth="0.5" />
      ))}

      {/* ── Corner bracket marks ─────────────────────────────── */}
      <path d="M40 70 L40 40 L70 40" stroke="#1C2A22" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M520 70 L520 40 L490 40" stroke="#1C2A22" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M40 530 L40 560 L70 560" stroke="#1C2A22" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M520 530 L520 560 L490 560" stroke="#1C2A22" strokeWidth="1.5" strokeLinecap="round"/>

      {/* ── Main stem ────────────────────────────────────────── */}
      <path
        d="M280 560 C280 480 275 400 280 300 C283 240 278 180 280 100"
        stroke="#1C2A22" strokeWidth="2" strokeLinecap="round"
      />

      {/* ── Large leaf — left ─────────────────────────────────── */}
      <path
        d="M278 320 C230 295 180 270 155 240 C175 225 220 235 260 260 C255 270 255 285 278 320Z"
        fill="#263830" opacity="0.85"
      />
      {/* leaf mid-vein */}
      <path d="M278 320 C255 285 220 260 155 240" stroke="#EEF1EB" strokeWidth="0.8" opacity="0.5"/>

      {/* ── Large leaf — right ────────────────────────────────── */}
      <path
        d="M281 285 C320 260 375 245 405 215 C388 200 342 208 305 232 C300 244 295 260 281 285Z"
        fill="#32493F" opacity="0.85"
      />
      <path d="M281 285 C300 255 340 230 405 215" stroke="#EEF1EB" strokeWidth="0.8" opacity="0.5"/>

      {/* ── Mid leaf — left ───────────────────────────────────── */}
      <path
        d="M279 230 C248 212 208 200 185 175 C202 162 242 174 270 196 C269 208 272 218 279 230Z"
        fill="#1C2A22" opacity="0.7"
      />
      <path d="M279 230 C265 210 232 185 185 175" stroke="#EEF1EB" strokeWidth="0.7" opacity="0.4"/>

      {/* ── Mid leaf — right ──────────────────────────────────── */}
      <path
        d="M281 200 C310 183 350 172 372 148 C356 136 318 148 291 170 C287 180 283 190 281 200Z"
        fill="#4A5E50" opacity="0.75"
      />
      <path d="M281 200 C291 175 325 155 372 148" stroke="#EEF1EB" strokeWidth="0.7" opacity="0.4"/>

      {/* ── Small top leaf ────────────────────────────────────── */}
      <path
        d="M280 130 C265 118 248 108 238 96 C250 88 267 96 278 112 L280 130Z"
        fill="#1C2A22" opacity="0.65"
      />
      <path
        d="M280 130 C295 118 312 108 322 96 C310 88 293 96 282 112 L280 130Z"
        fill="#263830" opacity="0.65"
      />

      {/* ── Small leaf pair — mid left ────────────────────────── */}
      <path
        d="M279 390 C258 378 234 368 218 352 C230 344 253 350 270 366 L279 390Z"
        fill="#32493F" opacity="0.7"
      />
      <path
        d="M281 380 C300 368 322 358 338 342 C326 334 304 340 288 355 L281 380Z"
        fill="#4A5E50" opacity="0.7"
      />

      {/* ── Sensor scatter nodes — upper cluster ──────────────── */}
      {/* These represent PCA/t-SNE data points */}
      <circle cx="120" cy="120" r="5" fill="#1C2A22" opacity="0.9"/>
      <circle cx="138" cy="108" r="3.5" fill="#4A5E50" opacity="0.8"/>
      <circle cx="148" cy="128" r="4" fill="#1C2A22" opacity="0.7"/>
      <circle cx="110" cy="138" r="3" fill="#8A9E90" opacity="0.9"/>
      <circle cx="128" cy="98"  r="2.5" fill="#32493F" opacity="0.8"/>
      <circle cx="158" cy="112" r="3" fill="#1C2A22" opacity="0.6"/>
      <circle cx="100" cy="112" r="2" fill="#4A5E50" opacity="0.7"/>

      {/* ── Sensor scatter nodes — lower-right cluster ────────── */}
      <circle cx="420" cy="420" r="5.5" fill="#1C2A22" opacity="0.85"/>
      <circle cx="438" cy="408" r="3.5" fill="#32493F" opacity="0.8"/>
      <circle cx="450" cy="430" r="4.5" fill="#4A5E50" opacity="0.75"/>
      <circle cx="410" cy="438" r="3" fill="#8A9E90" opacity="0.9"/>
      <circle cx="428" cy="398" r="3" fill="#1C2A22" opacity="0.7"/>
      <circle cx="460" cy="415" r="2.5" fill="#32493F" opacity="0.6"/>
      <circle cx="400" cy="415" r="2" fill="#4A5E50" opacity="0.8"/>

      {/* ── PCA axis lines ────────────────────────────────────── */}
      <line x1="85" y1="160" x2="180" y2="160" stroke="#1C2A22" strokeWidth="0.8" opacity="0.4"/>
      <line x1="132" y1="85"  x2="132" y2="175" stroke="#1C2A22" strokeWidth="0.8" opacity="0.4"/>
      {/* axis labels */}
      <text x="183" y="163" fontSize="8" fill="#8A9E90" fontFamily="monospace">PC1</text>
      <text x="135" y="83"  fontSize="8" fill="#8A9E90" fontFamily="monospace">PC2</text>

      {/* ── t-SNE axis lines (lower right) ───────────────────── */}
      <line x1="385" y1="460" x2="475" y2="460" stroke="#1C2A22" strokeWidth="0.8" opacity="0.4"/>
      <line x1="430" y1="385" x2="430" y2="465" stroke="#1C2A22" strokeWidth="0.8" opacity="0.4"/>
      <text x="478" y="463" fontSize="8" fill="#8A9E90" fontFamily="monospace">t-SNE1</text>
      <text x="432" y="382" fontSize="8" fill="#8A9E90" fontFamily="monospace">t-SNE2</text>

      {/* ── Waveform sensor trace ─────────────────────────────── */}
      <path
        d="M40 480 C70 480 80 455 100 455 C120 455 130 505 150 505
           C170 505 180 465 200 465 C220 465 230 490 250 490
           C265 490 270 475 280 475"
        stroke="#1C2A22" strokeWidth="1.5" strokeLinecap="round" opacity="0.35"
      />

      {/* ── Dotted connection lines between clusters ──────────── */}
      <line x1="150" y1="140" x2="260" y2="280"
            stroke="#8A9E90" strokeWidth="0.8" strokeDasharray="4 6" opacity="0.4"/>
      <line x1="400" y1="410" x2="295" y2="320"
            stroke="#8A9E90" strokeWidth="0.8" strokeDasharray="4 6" opacity="0.4"/>

      {/* ── Specimen label ─────────────────────────────────────── */}
      <rect x="40" y="540" width="135" height="22" rx="1" fill="#1C2A22" opacity="0.06"/>
      <text x="48" y="555" fontSize="9" fill="#1C2A22" opacity="0.55"
            fontFamily="monospace" letterSpacing="1">DRAVYA · SPECIMEN A</text>

      {/* ── Scale bar ──────────────────────────────────────────── */}
      <line x1="440" y1="555" x2="520" y2="555" stroke="#1C2A22" strokeWidth="1" opacity="0.35"/>
      <line x1="440" y1="551" x2="440" y2="559" stroke="#1C2A22" strokeWidth="1" opacity="0.35"/>
      <line x1="520" y1="551" x2="520" y2="559" stroke="#1C2A22" strokeWidth="1" opacity="0.35"/>
      <text x="466" y="548" fontSize="8" fill="#8A9E90" fontFamily="monospace">10 units</text>
    </svg>
  )
}
