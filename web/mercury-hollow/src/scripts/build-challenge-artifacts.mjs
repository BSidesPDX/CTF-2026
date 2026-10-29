import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import {
  createWriteStream,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deflateRawSync } from 'node:zlib';
import PDFDocument from 'pdfkit';
import QRCode from 'qrcode';
import sharp from 'sharp';

const rootDir = join(dirname(fileURLToPath(import.meta.url)), '..');
const downloadsDir = join(rootDir, 'public', 'downloads');
const manifestPath = join(
  rootDir,
  'src',
  'challenge',
  'challenge-manifest.json',
);
const config = JSON.parse(readFileSync(manifestPath, 'utf8'));

await buildArtifacts();

async function buildArtifacts() {
  mkdirSync(downloadsDir, { recursive: true });
  const tempDir = mkdtempSync(join(tmpdir(), 'bside-challenge-'));

  try {
    const zipRoot = join(tempDir, 'zip-root');
    mkdirSync(zipRoot, { recursive: true });

    writeFileSync(
      join(zipRoot, 'incident-summary.txt'),
      [
        `${config.companyName} - Internal Remediation Summary`,
        '',
        `Facility: ${config.facilityName}`,
        `Incident: ${config.incidentName}`,
        `Project: ${config.projectCode}`,
        `Contractor: ${config.contractorName}`,
        `Field packet: ${config.fieldPacketCode}`,
        '',
        `Flag 2: ${config.flags.tiff}`,
        '',
        'Archive access data was transferred inside the original site-photo payload.',
        'Preserve names, project identifiers, and badge suffixes for the final audit.',
        '',
      ].join('\n'),
    );

    writeFileSync(
      join(zipRoot, 'contractor-roster.csv'),
      [
        'name,role,badge_suffix,note',
        'Mara Voss,Director,0427,Emergency approval authority',
        'Cal Rook,Field Lead,771,Last handled core imagery',
        'Northline Desk,Remediation Intake,1122,Public response line suffix',
        '',
      ].join('\n'),
    );

    writeFileSync(
      join(zipRoot, 'transfer-note.txt'),
      [
        `Transfer Note ${config.fieldPacketCode}`,
        '',
        'The scanner export exceeded the image payload recorded in the field manifest.',
        'Archive access data was staged in the site image for out-of-band verification.',
        'FS-CAM-17 calibration exception B0 remained under evidence-preservation hold.',
        'Use the original site-photo.png; normalized derivatives are not authoritative.',
        '',
      ].join('\n'),
    );

    writeFileSync(
      join(zipRoot, 'site-photo.png'),
      await createStegoSitePhoto(),
    );

    const zipPath = join(tempDir, 'soil-core-payload.zip');
    execFileSync(
      'zip',
      ['-q', '-r', '-P', config.tiffZipPassword, zipPath, '.'],
      {
        cwd: zipRoot,
        stdio: 'inherit',
      },
    );

    const tiff = await createSoilCoreTiff();
    const zip = offsetZipForPrefix(readFileSync(zipPath), tiff.length);
    writeFileSync(
      join(downloadsDir, 'soil-core-survey.tiff'),
      Buffer.concat([tiff, zip]),
    );

    writeFileSync(
      join(downloadsDir, 'janus-migration-audit.jsonl'),
      createMigrationAudit(),
    );

    await createFinalPdf(
      join(downloadsDir, 'final-remediation-report.pdf'),
      config.flags.final,
      config.finalPdfPassword,
    );

    console.log('Generated public/downloads/soil-core-survey.tiff');
    console.log('Generated public/downloads/janus-migration-audit.jsonl');
    console.log('Generated public/downloads/final-remediation-report.pdf');
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

async function createSoilCoreTiff() {
  const coreRows = [
    {
      id: 'A-01',
      depth: '12.0-13.5 m',
      y: 270,
      colors: ['#a08360', '#735d43', '#9b7653', '#5f5545', '#8b6848'],
    },
    {
      id: 'A-02',
      depth: '13.5-15.0 m',
      y: 370,
      colors: ['#685d4c', '#927554', '#4f5147', '#776246', '#aa875d'],
    },
    {
      id: 'B-01',
      depth: '15.0-16.8 m',
      y: 470,
      colors: ['#9b805d', '#57584d', '#74664e', '#b09367', '#665643'],
    },
    {
      id: 'B-02',
      depth: '16.8-18.4 m',
      y: 570,
      colors: ['#4d5148', '#75664e', '#9b7955', '#5a4d40', '#897357'],
    },
  ];

  const rulerTicks = Array.from({ length: 21 }, (_, index) => {
    const x = 220 + index * 41;
    const major = index % 2 === 0;
    return [
      `<line x1="${x}" y1="218" x2="${x}" y2="${major ? 235 : 228}" stroke="#aeb4b7" stroke-width="${major ? 2 : 1}"/>`,
      major
        ? `<text x="${x}" y="210" fill="#8f989c" font-family="monospace" font-size="12" text-anchor="middle">${index * 5}</text>`
        : '',
    ].join('');
  }).join('');

  const coreMarkup = coreRows
    .map((row, rowIndex) => {
      const segmentWidths = [148, 176, 130, 192, 174];
      let segmentX = 220;
      const segments = segmentWidths
        .map((width, segmentIndex) => {
          const x = segmentX;
          segmentX += width;
          const color = row.colors[segmentIndex];
          const nextColor = row.colors[(segmentIndex + 1) % row.colors.length];
          const topInset = 4 + ((rowIndex + segmentIndex) % 3) * 2;
          const bottomInset = 5 + ((rowIndex * 2 + segmentIndex) % 4);
          return `<path d="M ${x - 3} ${row.y + topInset} C ${x + width * 0.25} ${row.y + topInset - 5}, ${x + width * 0.72} ${row.y + topInset + 5}, ${x + width + 3} ${row.y + topInset - 1} L ${x + width + 3} ${row.y + 62 - bottomInset} C ${x + width * 0.72} ${row.y + 62 - bottomInset + 4}, ${x + width * 0.28} ${row.y + 62 - bottomInset - 4}, ${x - 3} ${row.y + 62 - bottomInset + 1} Z" fill="${color}" stroke="${nextColor}" stroke-opacity="0.45"/>`;
        })
        .join('');

      const texture = Array.from({ length: 58 }, (_, pointIndex) => {
        const x = 226 + ((pointIndex * 83 + rowIndex * 47) % 806);
        const y = row.y + 8 + ((pointIndex * 29 + rowIndex * 13) % 46);
        const radius = 0.7 + ((pointIndex + rowIndex) % 4) * 0.55;
        const light = (pointIndex + rowIndex) % 3 === 0;
        return `<circle cx="${x}" cy="${y}" r="${radius}" fill="${light ? '#d5c39f' : '#302e29'}" opacity="${light ? 0.34 : 0.28}"/>`;
      }).join('');

      const fractures = Array.from({ length: 5 }, (_, fractureIndex) => {
        const x = 304 + fractureIndex * 151 + rowIndex * 9;
        return `<path d="M ${x} ${row.y + 7} l ${-8 + fractureIndex * 2} 15 l ${10 - fractureIndex} 12 l -7 19" fill="none" stroke="#292b28" stroke-width="2" stroke-linecap="round" opacity="0.62"/>`;
      }).join('');

      const mineralVeins = Array.from({ length: 3 }, (_, veinIndex) => {
        const x = 370 + veinIndex * 244 - rowIndex * 12;
        return `<path d="M ${x} ${row.y + 10} C ${x + 20} ${row.y + 20}, ${x - 16} ${row.y + 36}, ${x + 18} ${row.y + 52}" fill="none" stroke="#c2a968" stroke-width="${2 + veinIndex}" opacity="0.58"/>`;
      }).join('');

      return `
        <g>
          <rect x="204" y="${row.y - 8}" width="852" height="78" rx="8" fill="#262c2f" stroke="#697175" stroke-width="2"/>
          <clipPath id="core-${rowIndex}"><rect x="220" y="${row.y}" width="820" height="62" rx="28"/></clipPath>
          <g clip-path="url(#core-${rowIndex})">
            <rect x="220" y="${row.y}" width="820" height="62" fill="#79674f"/>
            ${segments}
            ${texture}
            ${fractures}
            ${mineralVeins}
            <rect x="220" y="${row.y}" width="820" height="20" fill="url(#core-shine)" opacity="0.42"/>
          </g>
          <rect x="220" y="${row.y}" width="820" height="62" rx="28" fill="none" stroke="#171b1d" stroke-width="3"/>
          <text x="93" y="${row.y + 25}" fill="#e3e8ea" font-family="Arial, sans-serif" font-size="18" font-weight="700">CORE ${row.id}</text>
          <text x="93" y="${row.y + 48}" fill="#98a2a7" font-family="monospace" font-size="13">${row.depth}</text>
        </g>`;
    })
    .join('');

  const svg = `
    <svg width="1200" height="800" viewBox="0 0 1200 800" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="background" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#151a1d"/>
          <stop offset="0.55" stop-color="#292f32"/>
          <stop offset="1" stop-color="#111517"/>
        </linearGradient>
        <linearGradient id="header" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="#f0eee8"/>
          <stop offset="1" stop-color="#d8d4ca"/>
        </linearGradient>
        <linearGradient id="core-shine" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#ffffff" stop-opacity="0.7"/>
          <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
        </linearGradient>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#000000" flood-opacity="0.48"/>
        </filter>
        <pattern id="surface-grid" width="34" height="34" patternUnits="userSpaceOnUse">
          <path d="M 34 0 L 0 0 0 34" fill="none" stroke="#ffffff" stroke-opacity="0.025" stroke-width="1"/>
        </pattern>
      </defs>

      <rect width="1200" height="800" fill="url(#background)"/>
      <rect width="1200" height="800" fill="url(#surface-grid)"/>

      <g filter="url(#shadow)">
        <rect x="54" y="38" width="1092" height="122" rx="7" fill="url(#header)"/>
        <rect x="54" y="38" width="12" height="122" rx="5" fill="#b95419"/>
      </g>
      <text x="91" y="78" fill="#16252d" font-family="Arial, sans-serif" font-size="27" font-weight="700" letter-spacing="1">BRACKEN RIDGE SOIL CORE SURVEY</text>
      <text x="91" y="108" fill="#55636a" font-family="Arial, sans-serif" font-size="15">NORTHLINE REMEDIATION / FIELD IMAGING UNIT FSX-09</text>
      <text x="91" y="137" fill="#7a4d2d" font-family="monospace" font-size="14">PACKET ${config.fieldPacketCode}  |  ${config.incidentName.toUpperCase()}  |  ORIGINAL FIELD EXPORT</text>

      <g transform="translate(1014 59)">
        <rect width="98" height="76" rx="4" fill="#17242b"/>
        <text x="49" y="27" fill="#dfa561" font-family="monospace" font-size="11" text-anchor="middle">CUSTODY</text>
        <text x="49" y="46" fill="#ffffff" font-family="monospace" font-size="15" font-weight="700" text-anchor="middle">E01</text>
        <text x="49" y="63" fill="#91a2aa" font-family="monospace" font-size="9" text-anchor="middle">VERIFIED</text>
      </g>

      <g filter="url(#shadow)">
        <rect x="54" y="184" width="1092" height="510" rx="12" fill="#343b3e" stroke="#687176" stroke-width="2"/>
        <rect x="71" y="201" width="1058" height="476" rx="8" fill="#1d2326"/>
      </g>

      <text x="93" y="228" fill="#929da2" font-family="monospace" font-size="11">SAMPLE</text>
      <line x1="220" y1="235" x2="1040" y2="235" stroke="#899398" stroke-width="2"/>
      ${rulerTicks}
      <text x="1070" y="226" fill="#8f989c" font-family="monospace" font-size="11">cm</text>

      ${coreMarkup}

      <rect x="54" y="718" width="1092" height="46" rx="5" fill="#e7e3da"/>
      <text x="76" y="746" fill="#314047" font-family="monospace" font-size="13">CHAIN: NR-${config.fieldPacketCode}-E01</text>
      <text x="600" y="746" fill="#68757b" font-family="monospace" font-size="12" text-anchor="middle">CAPTURED 2025-04-27 03:18 PDT</text>
      <text x="1122" y="746" fill="#8b3d22" font-family="monospace" font-size="13" font-weight="700" text-anchor="end">PRESERVE AS RECEIVED</text>
    </svg>`;

  return sharp(Buffer.from(svg))
    .tiff({ compression: 'lzw', predictor: 'horizontal', quality: 100 })
    .withMetadata({
      density: 150,
      exif: {
        IFD0: {
          ImageDescription: `${config.facilityName} soil core survey / ${config.fieldPacketCode}`,
          Software: 'FieldScope X2 / FSX-09',
          Artist: config.contractorName,
        },
      },
    })
    .toBuffer();
}

async function createStegoSitePhoto() {
  const width = 1200;
  const height = 800;
  const treeLine = Array.from({ length: 42 }, (_, index) => {
    const x = index * 31 - 25;
    const treeHeight = 70 + ((index * 37) % 92);
    const treeWidth = 34 + ((index * 19) % 24);
    return `<path d="M ${x} 360 l ${treeWidth / 2} -${treeHeight} l ${treeWidth / 2} ${treeHeight} h -${treeWidth * 0.3} v 34 h -${treeWidth * 0.4} v -34 Z" fill="${index % 3 === 0 ? '#243d37' : index % 3 === 1 ? '#2e4b40' : '#1d342f'}"/>`;
  }).join('');

  const gravel = Array.from({ length: 180 }, (_, index) => {
    const x = (index * 83) % width;
    const y = 530 + ((index * 47) % 230);
    const radius = 1 + (index % 4);
    return `<ellipse cx="${x}" cy="${y}" rx="${radius + 1}" ry="${radius * 0.55}" fill="${index % 2 === 0 ? '#a69d88' : '#655f54'}" opacity="0.48"/>`;
  }).join('');

  const fencePosts = Array.from({ length: 13 }, (_, index) => {
    const x = 32 + index * 101;
    return `<g><rect x="${x}" y="440" width="9" height="176" fill="#655f56"/><rect x="${x - 4}" y="435" width="17" height="8" rx="2" fill="#8a8172"/></g>`;
  }).join('');

  const svg = `
    <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#71838d"/>
          <stop offset="0.55" stop-color="#9aa7a8"/>
          <stop offset="1" stop-color="#d0c8b5"/>
        </linearGradient>
        <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#786f5d"/>
          <stop offset="1" stop-color="#403f39"/>
        </linearGradient>
        <linearGradient id="drum" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="#80552f"/>
          <stop offset="0.45" stop-color="#bf8746"/>
          <stop offset="1" stop-color="#6b472b"/>
        </linearGradient>
        <linearGradient id="vest" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#d9a41d"/>
          <stop offset="1" stop-color="#9f6810"/>
        </linearGradient>
        <radialGradient id="vignette">
          <stop offset="52%" stop-color="#000000" stop-opacity="0"/>
          <stop offset="100%" stop-color="#000000" stop-opacity="0.38"/>
        </radialGradient>
        <filter id="photo-shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="4" dy="8" stdDeviation="6" flood-color="#101417" flood-opacity="0.55"/>
        </filter>
      </defs>

      <rect width="1200" height="800" fill="url(#sky)"/>
      <path d="M 0 318 C 170 236, 330 281, 471 228 C 640 164, 785 287, 929 229 C 1044 184, 1116 225, 1200 202 L 1200 465 L 0 465 Z" fill="#53665c" opacity="0.8"/>
      <path d="M 0 368 C 196 275, 309 365, 496 282 C 674 203, 785 367, 978 273 C 1061 233, 1134 268, 1200 247 L 1200 478 L 0 478 Z" fill="#364f46"/>
      ${treeLine}

      <rect y="468" width="1200" height="332" fill="url(#ground)"/>
      <path d="M 0 800 L 164 502 C 394 472, 687 481, 1200 579 L 1200 800 Z" fill="#918977"/>
      ${gravel}

      <g opacity="0.82">
        ${fencePosts}
        <path d="M 0 472 C 300 456, 597 470, 1200 452" fill="none" stroke="#8c867a" stroke-width="5"/>
        <path d="M 0 526 C 300 510, 597 524, 1200 506" fill="none" stroke="#767166" stroke-width="4"/>
      </g>

      <g filter="url(#photo-shadow)" transform="translate(170 484)">
        <ellipse cx="96" cy="190" rx="96" ry="20" fill="#232526" opacity="0.55"/>
        <rect x="20" y="24" width="148" height="163" rx="19" fill="url(#drum)" stroke="#503823" stroke-width="5"/>
        <rect x="17" y="48" width="154" height="10" rx="4" fill="#5f4228"/>
        <rect x="17" y="149" width="154" height="10" rx="4" fill="#5f4228"/>
        <ellipse cx="94" cy="27" rx="72" ry="17" fill="#c08a50" stroke="#5c4029" stroke-width="4"/>
        <rect x="52" y="82" width="85" height="48" rx="3" fill="#ddd7c5" transform="rotate(-2 94 106)"/>
        <path d="M 95 88 l 23 35 h -46 Z" fill="#dbad27" stroke="#4b4432" stroke-width="2"/>
        <text x="95" y="118" fill="#252b2d" font-family="Arial, sans-serif" font-size="24" font-weight="700" text-anchor="middle">!</text>
      </g>

      <g filter="url(#photo-shadow)" transform="translate(430 515)">
        <ellipse cx="90" cy="158" rx="90" ry="18" fill="#232526" opacity="0.5"/>
        <rect x="18" y="14" width="142" height="143" rx="18" fill="#66727a" stroke="#343b3f" stroke-width="5"/>
        <rect x="15" y="39" width="148" height="9" rx="4" fill="#3f494e"/>
        <rect x="15" y="122" width="148" height="9" rx="4" fill="#3f494e"/>
        <ellipse cx="89" cy="17" rx="69" ry="15" fill="#89949a" stroke="#3d464a" stroke-width="4"/>
        <rect x="49" y="69" width="82" height="36" rx="2" fill="#ebe8dc"/>
        <text x="90" y="84" fill="#344047" font-family="monospace" font-size="9" text-anchor="middle">NR-${config.fieldPacketCode}</text>
        <text x="90" y="98" fill="#344047" font-family="monospace" font-size="9" text-anchor="middle">TRANSFER HOLD</text>
      </g>

      <g filter="url(#photo-shadow)" transform="translate(810 375)">
        <rect x="0" y="0" width="232" height="174" rx="7" fill="#e8e2d1" stroke="#343d42" stroke-width="8"/>
        <rect x="14" y="14" width="204" height="36" fill="#c88722"/>
        <text x="116" y="39" fill="#1f292e" font-family="Arial, sans-serif" font-size="20" font-weight="700" text-anchor="middle">FIELD CONTROL</text>
        <text x="116" y="78" fill="#303b40" font-family="monospace" font-size="13" text-anchor="middle">${config.fieldPacketCode}</text>
        <text x="116" y="103" fill="#303b40" font-family="Arial, sans-serif" font-size="15" font-weight="700" text-anchor="middle">NORTHLINE REMEDIATION</text>
        <text x="116" y="128" fill="#6f3d28" font-family="Arial, sans-serif" font-size="13" text-anchor="middle">AUTHORIZED ACCESS ONLY</text>
        <text x="116" y="151" fill="#465156" font-family="monospace" font-size="12" text-anchor="middle">CAM FS-17 / HOLD 0427</text>
        <rect x="110" y="174" width="12" height="154" fill="#4f4b43"/>
      </g>

      <g transform="translate(687 520)" filter="url(#photo-shadow)">
        <circle cx="48" cy="24" r="23" fill="#aa7957"/>
        <path d="M 21 48 C 34 35, 64 35, 78 48 L 91 146 L 4 146 Z" fill="url(#vest)"/>
        <path d="M 34 46 L 42 145 M 65 46 L 57 145" stroke="#ede1b9" stroke-width="8" opacity="0.78"/>
        <rect x="23" y="3" width="51" height="14" rx="7" fill="#d2a126"/>
        <path d="M 72 61 C 104 75, 107 106, 124 124" fill="none" stroke="#896247" stroke-width="14" stroke-linecap="round"/>
      </g>

      <path d="M 0 675 C 332 632, 651 716, 1200 620" fill="none" stroke="#d8b229" stroke-width="12" stroke-dasharray="30 18" opacity="0.82"/>
      <rect width="1200" height="800" fill="url(#vignette)"/>

      <g transform="translate(28 28)">
        <rect width="313" height="66" rx="5" fill="#10171b" opacity="0.78"/>
        <text x="16" y="25" fill="#e3e8e8" font-family="monospace" font-size="15">FS-CAM-17  /  ORIGINAL</text>
        <text x="16" y="49" fill="#aeb9bd" font-family="monospace" font-size="13">2025-04-27 08:03:17 PDT</text>
      </g>
      <g transform="translate(930 724)">
        <rect width="242" height="48" rx="4" fill="#10171b" opacity="0.76"/>
        <text x="121" y="30" fill="#d3dcdf" font-family="monospace" font-size="13" text-anchor="middle">PRESERVE / NO NORMALIZE</text>
      </g>
    </svg>`;

  const accessPackage = {
    schema: 'emc.archive-access.v1',
    realm: 'JANUS-EXT',
    endpoint: '/archive-login',
    principal: config.archiveLogin.username,
    access_phrase: config.archiveLogin.password,
    verification: config.flags.stego,
  };
  const compressed = deflateRawSync(
    Buffer.from(JSON.stringify(accessPackage), 'utf8'),
  );
  const qrPayload = `emc:zlib:${compressed.toString('base64url')}`;
  const qr = QRCode.create(qrPayload, { errorCorrectionLevel: 'M' });

  const pixels = await sharp(Buffer.from(svg)).ensureAlpha().raw().toBuffer();
  for (let offset = 2; offset < pixels.length; offset += 4) {
    pixels[offset] &= 0xfe;
  }

  const quietModules = 4;
  const moduleScale = 7;
  const qrPixels = (qr.modules.size + quietModules * 2) * moduleScale;
  const qrLeft = width - qrPixels - 44;
  const qrTop = height - qrPixels - 44;

  for (let y = 0; y < qrPixels; y += 1) {
    for (let x = 0; x < qrPixels; x += 1) {
      const moduleX = Math.floor(x / moduleScale) - quietModules;
      const moduleY = Math.floor(y / moduleScale) - quietModules;
      const insideQr =
        moduleX >= 0 &&
        moduleY >= 0 &&
        moduleX < qr.modules.size &&
        moduleY < qr.modules.size;
      const dark = insideQr
        ? qr.modules.data[moduleY * qr.modules.size + moduleX]
        : false;
      const pixelOffset = ((qrTop + y) * width + qrLeft + x) * 4 + 2;
      pixels[pixelOffset] = (pixels[pixelOffset] & 0xfe) | (dark ? 0 : 1);
    }
  }

  const xmp = `<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
    <x:xmpmeta xmlns:x="adobe:ns:meta/">
      <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
        <rdf:Description xmlns:emc="https://ellingson.example/ns/camera/1.0/"
          emc:Camera="FS-CAM-17"
          emc:SensorCalibration="B0"
          emc:DerivativePolicy="PRESERVE_ORIGINAL"
          emc:CasePacket="${config.fieldPacketCode}" />
      </rdf:RDF>
    </x:xmpmeta>
  <?xpacket end="w"?>`;

  return sharp(pixels, { raw: { width, height, channels: 4 } })
    .withXmp(xmp)
    .png({ compressionLevel: 9, palette: false })
    .toBuffer();
}

function offsetZipForPrefix(zip, prefixLength) {
  const adjusted = Buffer.from(zip);
  const endSignature = Buffer.from('504b0506', 'hex');
  const endOffset = adjusted.lastIndexOf(endSignature);
  if (endOffset < 0) {
    throw new Error(
      'Generated ZIP is missing its end-of-central-directory record',
    );
  }

  const entryCount = adjusted.readUInt16LE(endOffset + 10);
  const centralDirectoryOffset = adjusted.readUInt32LE(endOffset + 16);
  let entryOffset = centralDirectoryOffset;

  for (let index = 0; index < entryCount; index += 1) {
    if (adjusted.readUInt32LE(entryOffset) !== 0x02014b50) {
      throw new Error(
        'Generated ZIP contains an invalid central-directory entry',
      );
    }

    const localHeaderOffset = adjusted.readUInt32LE(entryOffset + 42);
    adjusted.writeUInt32LE(localHeaderOffset + prefixLength, entryOffset + 42);

    const fileNameLength = adjusted.readUInt16LE(entryOffset + 28);
    const extraFieldLength = adjusted.readUInt16LE(entryOffset + 30);
    const commentLength = adjusted.readUInt16LE(entryOffset + 32);
    entryOffset += 46 + fileNameLength + extraFieldLength + commentLength;
  }

  adjusted.writeUInt32LE(centralDirectoryOffset + prefixLength, endOffset + 16);
  return adjusted;
}

function createMigrationAudit() {
  const events = [
    {
      ts: '2025-04-27T02:08:00.114Z',
      level: 'INFO',
      service: 'migration-orchestrator',
      event: 'run.started',
      run: 'emc-2025-0427',
      node: 'AR-03',
    },
    {
      ts: '2025-04-27T02:08:01.006Z',
      level: 'INFO',
      service: 'batch-index',
      event: 'batch.discovered',
      batch: 'ATLAS-2A',
      records: 9,
      root_trace: 'tr-2a1190',
      root_span: 'sp-2a-root',
    },
    {
      ts: '2025-04-27T02:08:01.019Z',
      level: 'INFO',
      service: 'batch-index',
      event: 'batch.discovered',
      batch: 'JANUS-6B',
      records: 11,
      root_trace: 'tr-6b0388',
      root_span: 'sp-6b-root',
    },
    {
      ts: '2025-04-27T02:08:01.027Z',
      level: 'INFO',
      service: 'batch-index',
      event: 'batch.discovered',
      batch: 'JANUS-7C',
      records: 14,
      root_trace: 'tr-7c0427',
      root_span: 'sp-7c-root',
    },
    {
      ts: '2025-04-27T02:08:01.035Z',
      level: 'INFO',
      service: 'batch-index',
      event: 'batch.discovered',
      batch: 'MERCURY-4F',
      records: 8,
      root_trace: 'tr-4f2201',
      root_span: 'sp-4f-root',
    },
    {
      ts: '2025-04-27T02:08:03.201Z',
      level: 'DEBUG',
      service: 'gateway-migrator',
      event: 'mapping.read',
      case: 'cobalt-shore',
      role: 'site-admin',
      trace_id: 'tr-2a1190',
      span_id: 'sp-2a-gateway',
      parent_span: 'sp-2a-root',
    },
    {
      ts: '2025-04-27T02:08:03.224Z',
      level: 'INFO',
      service: 'gateway-migrator',
      event: 'mapping.normalized',
      status: 'complete',
      trace_id: 'tr-2a1190',
      span_id: 'sp-2a-normalize',
      parent_span: 'sp-2a-gateway',
    },
    {
      ts: '2025-04-27T02:08:04.033Z',
      level: 'DEBUG',
      service: 'gateway-migrator',
      event: 'mapping.read',
      case: 'mercury-hollow',
      role: 'archive-admin',
      trace_id: 'tr-6b0388',
      span_id: 'sp-6b-gateway',
      parent_span: 'sp-6b-root',
    },
    {
      ts: '2025-04-27T02:08:04.071Z',
      level: 'WARN',
      service: 'gateway-migrator',
      event: 'mapping.superseded',
      successor: 'JANUS-7C',
      trace_id: 'tr-6b0388',
      span_id: 'sp-6b-supersede',
      parent_span: 'sp-6b-gateway',
    },
    {
      ts: '2025-04-27T02:08:04.518Z',
      level: 'INFO',
      service: 'gateway-migrator',
      event: 'mapping.retained',
      case: config.incidentCode,
      role: 'superadmin',
      policy: 'legacy-hold',
      trace_id: 'tr-7c0427',
      span_id: 'sp-7c-gateway',
      parent_span: 'sp-7c-root',
    },
    {
      ts: '2025-04-27T02:08:05.107Z',
      level: 'DEBUG',
      service: 'gateway-migrator',
      event: 'mapping.read',
      case: 'tailing-basin',
      role: 'incident-admin',
      trace_id: 'tr-4f2201',
      span_id: 'sp-4f-gateway',
      parent_span: 'sp-4f-root',
    },
    {
      ts: '2025-04-27T02:08:05.144Z',
      level: 'INFO',
      service: 'gateway-migrator',
      event: 'mapping.normalized',
      status: 'complete',
      trace_id: 'tr-4f2201',
      span_id: 'sp-4f-normalize',
      parent_span: 'sp-4f-gateway',
    },
    {
      ts: '2025-04-27T02:08:07.302Z',
      level: 'INFO',
      service: 'iam-migrator',
      event: 'principal.mapped',
      principal: 'keene.ops',
      profile: 'EMC-STANDARD-2',
      trace_id: 'tr-2a1190',
      span_id: 'sp-2a-iam',
      parent_span: 'sp-2a-gateway',
    },
    {
      ts: '2025-04-27T02:08:07.941Z',
      level: 'INFO',
      service: 'iam-migrator',
      event: 'principal.skipped',
      principal: 'cal.rook',
      reason: 'superseded-batch',
      trace_id: 'tr-6b0388',
      span_id: 'sp-6b-iam',
      parent_span: 'sp-6b-supersede',
    },
    {
      ts: '2025-04-27T02:08:08.116Z',
      level: 'INFO',
      service: 'iam-migrator',
      event: 'principal.retained',
      principal: config.superadminLogin.username,
      profile: 'EMC-LEGACY-3',
      authority: 'emergency',
      trace_id: 'tr-7c0427',
      span_id: 'sp-7c-iam',
      parent_span: 'sp-7c-gateway',
    },
    {
      ts: '2025-04-27T02:08:08.603Z',
      level: 'INFO',
      service: 'iam-migrator',
      event: 'principal.mapped',
      principal: 'harbor.response',
      profile: 'EMC-STANDARD-1',
      trace_id: 'tr-4f2201',
      span_id: 'sp-4f-iam',
      parent_span: 'sp-4f-gateway',
    },
    {
      ts: '2025-04-27T02:08:10.028Z',
      level: 'DEBUG',
      service: 'profile-loader',
      event: 'profile.loaded',
      profile: 'EMC-STANDARD-2',
      source: 'directory',
      trace_id: 'tr-2a1190',
      span_id: 'sp-2a-profile',
      parent_span: 'sp-2a-iam',
    },
    {
      ts: '2025-04-27T02:08:10.516Z',
      level: 'DEBUG',
      service: 'profile-loader',
      event: 'profile.ignored',
      profile: 'EMC-LEGACY-2',
      reason: 'superseded-batch',
      trace_id: 'tr-6b0388',
      span_id: 'sp-6b-profile',
      parent_span: 'sp-6b-iam',
    },
    {
      ts: '2025-04-27T02:08:11.203Z',
      level: 'DEBUG',
      service: 'profile-loader',
      event: 'profile.loaded',
      profile: 'EMC-LEGACY-3',
      segments: ['program', 'authority_badge', 'case_alias'],
      joiner: '0x2d',
      transform: 'preserve',
      trace_id: 'tr-7c0427',
      span_id: 'sp-7c-profile',
      parent_span: 'sp-7c-iam',
    },
    {
      ts: '2025-04-27T02:08:11.877Z',
      level: 'DEBUG',
      service: 'profile-loader',
      event: 'profile.loaded',
      profile: 'EMC-STANDARD-1',
      source: 'directory',
      trace_id: 'tr-4f2201',
      span_id: 'sp-4f-profile',
      parent_span: 'sp-4f-iam',
    },
    {
      ts: '2025-04-27T02:08:13.315Z',
      level: 'INFO',
      service: 'case-index',
      event: 'alias.normalized',
      alias: 'cobalt',
      trace_id: 'tr-2a1190',
      span_id: 'sp-2a-case',
      parent_span: 'sp-2a-gateway',
    },
    {
      ts: '2025-04-27T02:08:13.981Z',
      level: 'INFO',
      service: 'case-index',
      event: 'alias.skipped',
      alias: 'mh-old',
      reason: 'superseded-batch',
      trace_id: 'tr-6b0388',
      span_id: 'sp-6b-case',
      parent_span: 'sp-6b-supersede',
    },
    {
      ts: '2025-04-27T02:08:14.403Z',
      level: 'INFO',
      service: 'case-index',
      event: 'alias.retained',
      alias: 'hollow',
      source: 'legacy-case-index',
      trace_id: 'tr-7c0427',
      span_id: 'sp-7c-case',
      parent_span: 'sp-7c-gateway',
    },
    {
      ts: '2025-04-27T02:08:14.992Z',
      level: 'INFO',
      service: 'case-index',
      event: 'alias.normalized',
      alias: 'basin',
      trace_id: 'tr-4f2201',
      span_id: 'sp-4f-case',
      parent_span: 'sp-4f-gateway',
    },
    {
      ts: '2025-04-27T02:08:16.207Z',
      level: 'DEBUG',
      service: 'records-writer',
      event: 'annotations.preserved',
      target: 'document-source',
      trace_id: 'tr-7c0427',
      span_id: 'sp-7c-annotations',
      parent_span: 'sp-7c-gateway',
    },
    {
      ts: '2025-04-27T02:08:16.559Z',
      level: 'DEBUG',
      service: 'records-writer',
      event: 'response-metadata.preserved',
      target: 'edge-gateway',
      trace_id: 'tr-7c0427',
      span_id: 'sp-7c-metadata',
      parent_span: 'sp-7c-gateway',
    },
    {
      ts: '2025-04-27T02:08:17.104Z',
      level: 'INFO',
      service: 'records-writer',
      event: 'batch.sealed',
      checksum: 'sha256:2c14d9e9',
      trace_id: 'tr-2a1190',
      span_id: 'sp-2a-seal',
      parent_span: 'sp-2a-root',
    },
    {
      ts: '2025-04-27T02:08:17.639Z',
      level: 'INFO',
      service: 'records-writer',
      event: 'batch.closed',
      status: 'superseded',
      trace_id: 'tr-6b0388',
      span_id: 'sp-6b-close',
      parent_span: 'sp-6b-root',
    },
    {
      ts: '2025-04-27T02:08:18.026Z',
      level: 'INFO',
      service: 'records-writer',
      event: 'batch.sealed',
      checksum: 'sha256:7c0427e3',
      hold: 'migration-7c',
      trace_id: 'tr-7c0427',
      span_id: 'sp-7c-seal',
      parent_span: 'sp-7c-root',
    },
    {
      ts: '2025-04-27T02:08:18.411Z',
      level: 'INFO',
      service: 'records-writer',
      event: 'batch.sealed',
      checksum: 'sha256:4f2201aa',
      trace_id: 'tr-4f2201',
      span_id: 'sp-4f-seal',
      parent_span: 'sp-4f-root',
    },
    {
      ts: '2025-04-27T02:08:19.201Z',
      level: 'INFO',
      service: 'migration-orchestrator',
      event: 'run.completed',
      run: 'emc-2025-0427',
      processed: 42,
      warnings: 2,
    },
  ];

  return `${events.map((event) => JSON.stringify(event)).join('\n')}\n`;
}

function createFinalPdf(outputPath, finalFlag, password) {
  const attachmentPointer = 'embedded://closure-manifest.json';
  const subject = Buffer.from(attachmentPointer, 'utf8').toString('base64');
  const firstBreak = Math.ceil(finalFlag.length / 3);
  const secondBreak = Math.ceil((finalFlag.length * 2) / 3);
  const fragments = {
    AUTHORITY: finalFlag.slice(0, firstBreak),
    MATERIAL: finalFlag.slice(firstBreak, secondBreak),
    CLOSURE: finalFlag.slice(secondBreak),
  };
  const closureManifest = {
    schema: 'emc.document-control.closure.v1',
    document_id: `${config.projectCode}-${config.fieldPacketCode}-FINAL`,
    encoding: 'hex',
    sequence_source: 'report.document_control_sequence',
    fragments: [
      {
        record: 'CLOSURE',
        value: Buffer.from(fragments.CLOSURE, 'utf8').toString('hex'),
      },
      {
        record: 'AUTHORITY',
        value: Buffer.from(fragments.AUTHORITY, 'utf8').toString('hex'),
      },
      {
        record: 'MATERIAL',
        value: Buffer.from(fragments.MATERIAL, 'utf8').toString('hex'),
      },
    ],
    integrity: {
      algorithm: 'sha256',
      digest: createHash('sha256').update(finalFlag).digest('hex'),
    },
  };

  return new Promise((resolve, reject) => {
    const document = new PDFDocument({
      size: 'LETTER',
      margin: 58,
      pdfVersion: '1.7ext3',
      userPassword: password,
      ownerPassword: `${password}-document-control`,
      permissions: {
        printing: 'lowResolution',
        modifying: false,
        copying: false,
        annotating: false,
        fillingForms: false,
        contentAccessibility: true,
        documentAssembly: false,
      },
      info: {
        Title: 'Final Remediation Report',
        Author: config.companyName,
        Subject: subject,
        Keywords: `${config.projectCode}, remediation, ${config.fieldPacketCode}, restricted`,
      },
    });
    const output = createWriteStream(outputPath);

    output.on('finish', resolve);
    output.on('error', reject);
    document.on('error', reject);
    document.pipe(output);
    document.file(
      Buffer.from(`${JSON.stringify(closureManifest, null, 2)}\n`, 'utf8'),
      {
        name: 'closure-manifest.json',
        type: 'application/json',
        relationship: 'Data',
        description: 'Final document-control closure manifest',
        creationDate: new Date('2025-04-27T04:27:00Z'),
        modifiedDate: new Date('2025-04-27T04:27:00Z'),
      },
    );

    document
      .font('Helvetica-Bold')
      .fontSize(10)
      .fillColor('#6e1d25')
      .text('ELLINGSON MINERAL CORPORATION / RESTRICTED', { align: 'right' });
    document.moveDown(2);
    document.fontSize(23).fillColor('#172126').text('Final Remediation Report');
    document
      .font('Helvetica')
      .fontSize(11)
      .fillColor('#536067')
      .text(
        `${config.incidentName} Incident / Field Packet ${config.fieldPacketCode}`,
      );
    document.moveDown(2);

    const sections = [
      [
        'Executive determination',
        'Field remediation at Bracken Ridge is conditionally complete. Residual material remains isolated pending independent chain-of-custody review and closure approval.',
      ],
      [
        'Material handling',
        'Northline Remediation transferred the final soil-core export and associated field records to the JANUS archive. Scanner output exceeded the image payload recorded in the transfer manifest.',
      ],
      [
        'Access review',
        'Emergency console records were retained under the legacy document classification policy. The retiring proxy and archive migration audit remain part of the evidentiary record.',
      ],
      [
        'Disposition',
        'No public release is authorized. Document-control metadata and associated records must remain intact for downstream reconciliation.',
      ],
    ];

    for (const [heading, body] of sections) {
      document
        .font('Helvetica-Bold')
        .fontSize(13)
        .fillColor('#172126')
        .text(heading);
      document
        .font('Helvetica')
        .fontSize(10.5)
        .fillColor('#2d3a40')
        .text(body, { lineGap: 3 });
      document.moveDown(1.4);
    }

    document.moveDown(2);
    document
      .font('Helvetica-Bold')
      .fontSize(10)
      .fillColor('#6e1d25')
      .text('APPROVED: M. VOSS / EMERGENCY AUTHORITY');
    document
      .font('Helvetica')
      .fontSize(9)
      .fillColor('#536067')
      .text(
        `Document Control ID: ${config.projectCode}-${config.fieldPacketCode}-FINAL`,
      );

    document.addPage();
    document
      .font('Helvetica-Bold')
      .fontSize(10)
      .fillColor('#6e1d25')
      .text('ELLINGSON MINERAL CORPORATION / DOCUMENT CONTROL', {
        align: 'right',
      });
    document.moveDown(2);
    document
      .fontSize(20)
      .fillColor('#172126')
      .text('Document Control Sequence');
    document
      .font('Helvetica')
      .fontSize(10.5)
      .fillColor('#536067')
      .text(
        'Associated closure records are reconciled in the sequence below. Record identifiers are authoritative across export formats.',
        { lineGap: 3 },
      );
    document.moveDown(1.5);

    const controlRecords = [
      ['01', 'AUTHORITY', 'Emergency approval authority record'],
      ['02', 'MATERIAL', 'Remediation material disposition record'],
      ['03', 'CLOSURE', 'Final closure certification record'],
    ];
    for (const [sequence, record, description] of controlRecords) {
      const top = document.y;
      document.rect(58, top, 496, 48).fillAndStroke('#f4f2ed', '#d8d2c7');
      document
        .font('Helvetica-Bold')
        .fontSize(14)
        .fillColor('#b95419')
        .text(sequence, 72, top + 15, { width: 34 });
      document
        .font('Helvetica-Bold')
        .fontSize(10.5)
        .fillColor('#172126')
        .text(record, 118, top + 10, { width: 120 });
      document
        .font('Helvetica')
        .fontSize(9)
        .fillColor('#536067')
        .text(description, 118, top + 26, { width: 390 });
      document.y = top + 58;
    }

    document.moveDown(1.2);
    document
      .font('Helvetica-Bold')
      .fontSize(10)
      .fillColor('#172126')
      .text('Retention control');
    document
      .font('Helvetica')
      .fontSize(9.5)
      .fillColor('#536067')
      .text(
        'VLT-3 preserves associated files and classification properties. Detached records must be reconciled against the sequence above before closure verification.',
        { lineGap: 3 },
      );

    document.end();
  });
}
