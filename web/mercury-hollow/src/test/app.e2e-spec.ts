import { Test, TestingModule } from '@nestjs/testing';
import { NestExpressApplication } from '@nestjs/platform-express';
import request from 'supertest';
import { configureApplication } from '../src/app.setup';
import { ChallengeModule } from '../src/challenge/challenge.module';
import manifest from '../src/challenge/challenge-manifest.json';

describe('Challenge flow (e2e)', () => {
  let app: NestExpressApplication;

  beforeAll(async () => {
    process.env.NODE_ENV = 'test';
    process.env.SESSION_SECRET = 'test-session-secret';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [ChallengeModule],
    }).compile();

    app = moduleFixture.createNestApplication<NestExpressApplication>();
    configureApplication(app);
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  it('requires each stage and supports the complete author solve', async () => {
    const agent = request.agent(app.getHttpServer());

    await agent.get('/health').expect(200, {
      status: 'ok',
      artifactsReady: true,
    });
    const incident = await agent.get('/incident').expect(200);
    expect(incident.text).toContain(`${manifest.incidentName} Response Update`);
    expect(incident.text).toContain('Authorized Partner Access');
    expect(incident.text).toContain('/images/dump-site-a.jpg');
    expect(incident.text).toContain('/images/dump-site-b.jpg');
    expect(incident.text).toContain('/images/dump-site-c.jpg');
    expect(incident.text).not.toContain('Inspect the roadside');
    expect(incident.text).not.toContain('Inventory labels often carry');
    expect(incident.text).not.toContain('Contractor Login</a>');
    expect(incident.text).not.toContain('Exercise Scope');
    await agent
      .get('/challenge-downloads/soil-core-survey.tiff')
      .expect(302)
      .expect('Location', '/contractor-login');

    await agent
      .post('/contractor-login')
      .type('form')
      .send(manifest.contractorLogin)
      .expect(302)
      .expect('Location', '/contractor');
    const contractor = await agent.get('/contractor').expect(200);
    expect(contractor.text).toContain(manifest.flags.phone);
    expect(contractor.text).toContain('EX-17 / BOUNDARY MISMATCH');
    expect(contractor.text).toContain('Profile NDR-4.2');
    expect(contractor.text).toContain('BRACKEN');
    expect(contractor.text).not.toContain('unexplained trailing data');
    expect(contractor.text).not.toContain('Retention passphrase policy');
    await agent.get('/challenge-downloads/soil-core-survey.tiff').expect(200);

    const archiveLogin = await agent.get('/archive-login').expect(200);
    expect(archiveLogin.text).toContain('JANUS Records Exchange');
    expect(archiveLogin.text).toContain('Archive Principal');
    expect(archiveLogin.text).not.toContain('Unlock Archive');

    await agent
      .post('/archive-login')
      .type('form')
      .send(manifest.archiveLogin)
      .expect(302)
      .expect('Location', '/archive');
    const archive = await agent.get('/archive').expect(200);
    expect(archive.headers['x-janus-namespace']).toBe(manifest.facilityCode);
    expect(archive.text).toContain(manifest.flags.stego);
    expect(archive.text).toContain('/ops/{namespace}/{case-slug}/{role}');
    expect(archive.text).toContain('Emergency Controls Migration Set 7C');
    expect(archive.text).toContain('Archive Node AR-03');
    expect(archive.text).not.toContain('Preserve headers and source');
    expect(archive.text).not.toContain('old route was split');
    expect(archive.text).not.toContain(manifest.superadminRoute);
    const auditDownload = await agent
      .get('/challenge-downloads/janus-migration-audit.jsonl')
      .expect(200);
    expect(auditDownload.headers['content-disposition']).toContain(
      'janus-migration-audit.jsonl',
    );

    const superadminLogin = await agent
      .get(manifest.superadminRoute)
      .expect(200);
    expect(superadminLogin.text).toContain(
      'Emergency Operations Control Plane',
    );
    expect(superadminLogin.text).toContain('Authority Principal');
    expect(superadminLogin.text).not.toContain('Superadmin Challenge');
    await agent
      .post(manifest.superadminRoute)
      .type('form')
      .send(manifest.superadminLogin)
      .expect(302)
      .expect('Location', manifest.superadminRoute);
    const superadmin = await agent.get(manifest.superadminRoute).expect(200);
    expect(superadmin.text).toContain(manifest.flags.superadmin);
    expect(superadmin.text).toContain('Final Remediation Report');
    expect(superadmin.text).toContain('VLT-3 Legacy Control');
    expect(superadmin.text).toContain('INCIDENT.CONSTITUENT');
    expect(superadmin.text).toContain('ARCHIVE.BATCH_FAMILY');
    expect(superadmin.text).toContain('CUSTODY.PACKET_SUFFIX');
    expect(superadmin.text).toContain('0x2D');
    expect(superadmin.text).toContain('Classification fields retained');
    expect(superadmin.text).not.toContain('<code>MERCURY</code>');
    expect(superadmin.text).not.toContain('<code>0427</code>');
    expect(superadmin.text).not.toContain('Vault passphrases use');
    expect(superadmin.text).not.toContain('Those values appeared');
    await agent
      .get('/challenge-downloads/final-remediation-report.pdf')
      .expect(200)
      .expect('Content-Type', /application\/pdf/);
  });

  it('does not reveal the hidden route through the final download gate', async () => {
    await request(app.getHttpServer())
      .get('/challenge-downloads/final-remediation-report.pdf')
      .expect(302)
      .expect('Location', '/archive-login');
  });

  it('rejects invalid credentials without recording sensitive values', async () => {
    const response = await request(app.getHttpServer())
      .post('/contractor-login')
      .type('form')
      .send({ username: 'wrong', password: 'wrong' })
      .expect(401);
    expect(response.text).toContain('Contractor credentials rejected');
  });
});
