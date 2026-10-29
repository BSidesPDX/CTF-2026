import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { inflateRawSync } from 'node:zlib';
import jsQR from 'jsqr';
import sharp from 'sharp';

const rootDir = join(dirname(fileURLToPath(import.meta.url)), '..');
const downloadsDir = join(rootDir, 'public', 'downloads');
const config = JSON.parse(
  readFileSync(
    join(rootDir, 'src', 'challenge', 'challenge-manifest.json'),
    'utf8',
  ),
);

await validateTiffArchive();
validateMigrationAudit();
validateFinalPdf();
console.log('Challenge artifacts passed author validation');

async function validateTiffArchive() {
  const tiffPath = join(downloadsDir, 'soil-core-survey.tiff');
  const tiff = readFileSync(tiffPath);
  assert.ok(
    ['49492a00', '4d4d002a'].includes(tiff.subarray(0, 4).toString('hex')),
    'Soil-core artifact does not begin with a TIFF signature',
  );

  const metadata = await sharp(tiff).metadata();
  assert.equal(metadata.format, 'tiff');
  assert.ok(
    (metadata.width ?? 0) >= 1200,
    'Soil-core TIFF is not wide enough to be a field survey image',
  );
  assert.ok(
    (metadata.height ?? 0) >= 800,
    'Soil-core TIFF is not tall enough to be a field survey image',
  );
  assert.ok(
    (metadata.channels ?? 0) >= 3,
    'Soil-core TIFF is not a color image',
  );

  const zipOffset = tiff.lastIndexOf(Buffer.from('504b0304', 'hex'));
  assert.ok(zipOffset > 0, 'TIFF does not contain an appended ZIP archive');

  const tempDir = mkdtempSync(join(tmpdir(), 'bside-artifact-check-'));
  try {
    const extractedDir = join(tempDir, 'extracted');
    execFileSync(
      'unzip',
      ['-qq', '-P', config.tiffZipPassword, tiffPath, '-d', extractedDir],
      { stdio: 'pipe' },
    );

    const incidentSummary = readFileSync(
      join(extractedDir, 'incident-summary.txt'),
      'utf8',
    );
    const sitePhotoPath = join(extractedDir, 'site-photo.png');
    const sitePhoto = readFileSync(sitePhotoPath);
    assert.match(incidentSummary, new RegExp(escapeRegex(config.flags.tiff)));
    assert.ok(
      !sitePhoto.includes(Buffer.from(config.archiveLogin.username)),
      'Archive principal is stored plainly in the site photo',
    );
    assert.ok(
      !sitePhoto.includes(Buffer.from(config.archiveLogin.password)),
      'Archive access phrase is stored plainly in the site photo',
    );

    const photoMetadata = await sharp(sitePhoto).metadata();
    assert.equal(photoMetadata.format, 'png');
    assert.equal(photoMetadata.width, 1200);
    assert.equal(photoMetadata.height, 800);
    assert.match(photoMetadata.xmpAsString ?? '', /SensorCalibration="B0"/);

    const { data: photoPixels, info: photoInfo } = await sharp(sitePhoto)
      .ensureAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });
    const bitPlane = new Uint8ClampedArray(
      photoInfo.width * photoInfo.height * 4,
    );
    for (
      let pixel = 0;
      pixel < photoInfo.width * photoInfo.height;
      pixel += 1
    ) {
      const value = (photoPixels[pixel * 4 + 2] & 1) === 1 ? 255 : 0;
      bitPlane[pixel * 4] = value;
      bitPlane[pixel * 4 + 1] = value;
      bitPlane[pixel * 4 + 2] = value;
      bitPlane[pixel * 4 + 3] = 255;
    }

    const qr = jsQR(bitPlane, photoInfo.width, photoInfo.height, {
      inversionAttempts: 'attemptBoth',
    });
    assert.ok(qr, 'Blue bit-plane does not contain a readable QR code');
    assert.match(qr.data, /^emc:zlib:/);

    const accessPackage = JSON.parse(
      inflateRawSync(
        Buffer.from(qr.data.replace(/^emc:zlib:/, ''), 'base64url'),
      ).toString('utf8'),
    );
    assert.equal(accessPackage.endpoint, '/archive-login');
    assert.equal(accessPackage.principal, config.archiveLogin.username);
    assert.equal(accessPackage.access_phrase, config.archiveLogin.password);
    assert.equal(accessPackage.verification, config.flags.stego);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

function validateMigrationAudit() {
  const audit = readFileSync(
    join(downloadsDir, 'janus-migration-audit.jsonl'),
    'utf8',
  );
  const events = audit
    .trim()
    .split('\n')
    .map((line, index) => {
      try {
        return JSON.parse(line);
      } catch (error) {
        throw new Error(`Migration audit line ${index + 1} is not JSON`, {
          cause: error,
        });
      }
    });

  assert.ok(
    events.length >= 30,
    'Migration audit does not contain enough noise',
  );
  const batches = new Set(events.map((event) => event.batch).filter(Boolean));
  assert.ok(
    batches.size >= 4,
    'Migration audit does not contain enough batches',
  );

  const batchRoot = events.find(
    (event) => event.event === 'batch.discovered' && event.batch === 'JANUS-7C',
  );
  assert.ok(batchRoot?.root_trace, 'JANUS-7C does not expose a root trace');
  assert.ok(batchRoot?.root_span, 'JANUS-7C does not expose a root span');
  assert.equal(
    events.filter((event) => event.batch === 'JANUS-7C').length,
    1,
    'JANUS-7C child events can still be recovered by filtering only on batch',
  );

  const relevant = events.filter(
    (event) => event.trace_id === batchRoot.root_trace,
  );
  const gateway = relevant.find(
    (event) =>
      event.service === 'gateway-migrator' &&
      event.event === 'mapping.retained',
  );
  assert.ok(
    gateway &&
      gateway.case === config.incidentCode &&
      gateway.role === 'superadmin' &&
      gateway.parent_span === batchRoot.root_span,
    'Migration audit is missing the retained route mapping',
  );

  const principal = relevant.find(
    (event) =>
      event.service === 'iam-migrator' && event.event === 'principal.retained',
  );
  assert.ok(
    principal &&
      principal.principal === config.superadminLogin.username &&
      principal.profile === 'EMC-LEGACY-3' &&
      principal.parent_span === gateway.span_id,
    'Migration audit is missing the retained principal',
  );

  const profile = relevant.find(
    (event) =>
      event.service === 'profile-loader' && event.event === 'profile.loaded',
  );
  assert.ok(
    profile &&
      profile.joiner === '0x2d' &&
      profile.parent_span === principal.span_id &&
      JSON.stringify(profile.segments) ===
        JSON.stringify(['program', 'authority_badge', 'case_alias']),
    'Migration audit is missing the credential profile',
  );

  const caseAlias = relevant.find(
    (event) =>
      event.service === 'case-index' && event.event === 'alias.retained',
  );
  assert.ok(
    caseAlias &&
      caseAlias.alias === 'hollow' &&
      caseAlias.parent_span === gateway.span_id,
    'Migration audit is missing the retained case alias',
  );

  assert.ok(
    !audit.includes(config.superadminLogin.password),
    'Migration audit contains the finished superadmin password',
  );
  assert.ok(
    !audit.includes('credential-format'),
    'Migration audit contains an answer-shaped credential format',
  );
}

function validateFinalPdf() {
  const pdfPath = join(downloadsDir, 'final-remediation-report.pdf');
  const pdf = readFileSync(pdfPath);
  const rawPdf = pdf.toString('latin1');
  const attachmentPointer = 'embedded://closure-manifest.json';
  const encodedPointer = Buffer.from(attachmentPointer, 'utf8').toString(
    'base64',
  );
  const encodedFlag = Buffer.from(config.flags.final, 'utf8').toString(
    'base64',
  );

  assert.ok(rawPdf.startsWith('%PDF-'), 'Final report is not a PDF');
  assert.match(rawPdf, /\/Encrypt\b/, 'Final report is not password-protected');
  assert.ok(
    !rawPdf.includes(config.flags.final),
    'Final flag is stored in plaintext',
  );
  assert.ok(
    !rawPdf.includes(encodedFlag),
    'Encoded final flag is stored in plaintext',
  );

  const pdfInfo = spawnSync(
    'pdfinfo',
    ['-upw', config.finalPdfPassword, pdfPath],
    { encoding: 'utf8' },
  );
  if (!pdfInfo.error) {
    assert.equal(pdfInfo.status, 0, pdfInfo.stderr);
    assert.match(pdfInfo.stdout, /Pages:\s+2\b/);
    assert.match(pdfInfo.stdout, new RegExp(escapeRegex(encodedPointer)));
    assert.ok(
      !pdfInfo.stdout.includes(encodedFlag),
      'Unlocked PDF metadata exposes the final flag directly',
    );

    const wrongPassword = spawnSync('pdfinfo', ['-upw', 'wrong', pdfPath], {
      encoding: 'utf8',
    });
    assert.notEqual(
      wrongPassword.status,
      0,
      'PDF accepted an invalid password',
    );
  }

  const attachmentList = spawnSync(
    'pdfdetach',
    ['-upw', config.finalPdfPassword, '-list', pdfPath],
    { encoding: 'utf8' },
  );
  if (!attachmentList.error) {
    assert.equal(attachmentList.status, 0, attachmentList.stderr);
    assert.match(attachmentList.stdout, /closure-manifest\.json/);

    const tempDir = mkdtempSync(join(tmpdir(), 'bside-pdf-check-'));
    try {
      const manifestPath = join(tempDir, 'closure-manifest.json');
      const extraction = spawnSync(
        'pdfdetach',
        [
          '-upw',
          config.finalPdfPassword,
          '-savefile',
          'closure-manifest.json',
          '-o',
          manifestPath,
          pdfPath,
        ],
        { encoding: 'utf8' },
      );
      assert.equal(extraction.status, 0, extraction.stderr);

      const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
      assert.equal(manifest.encoding, 'hex');
      assert.equal(
        manifest.sequence_source,
        'report.document_control_sequence',
      );
      assert.deepEqual(
        manifest.fragments.map((fragment) => fragment.record),
        ['CLOSURE', 'AUTHORITY', 'MATERIAL'],
        'Closure manifest fragments are not shuffled',
      );

      const byRecord = new Map(
        manifest.fragments.map((fragment) => [
          fragment.record,
          Buffer.from(fragment.value, 'hex').toString('utf8'),
        ]),
      );
      const assembled = ['AUTHORITY', 'MATERIAL', 'CLOSURE']
        .map((record) => byRecord.get(record))
        .join('');
      assert.equal(assembled, config.flags.final);
      assert.equal(
        manifest.integrity.digest,
        createHash('sha256').update(assembled).digest('hex'),
      );
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  }
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
