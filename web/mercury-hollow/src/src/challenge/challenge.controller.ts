import { Body, Controller, Get, Post, Req, Res } from '@nestjs/common';
import type { Request, Response } from 'express';
import { join } from 'path';
import {
  ArchiveLoginDto,
  ContractorLoginDto,
  SuperadminLoginDto,
} from './challenge.dto';
import { ChallengeService } from './challenge.service';
import { ChallengeTelemetryService } from './challenge-telemetry.service';

type ChallengeSession = Request['session'] & {
  contractorAccess?: boolean;
  archiveAccess?: boolean;
  superadminAccess?: boolean;
};

@Controller()
export class ChallengeController {
  constructor(
    private readonly challengeService: ChallengeService,
    private readonly telemetry: ChallengeTelemetryService,
  ) {}

  @Get('challenge-brief')
  challengeBrief(@Res() res: Response) {
    return res.render('challenge-brief', {
      title: 'Incident Challenge Brief',
    });
  }

  @Get('incident')
  incident(@Res() res: Response) {
    const config = this.challengeService.getConfig();
    return res.render('incident', {
      title: 'Environmental Response Bulletin',
      companyName: config.companyName,
      contractorName: config.contractorName,
      facilityName: config.facilityName,
      incidentName: config.incidentName,
      fieldPacketCode: config.fieldPacketCode,
      photoSlots: [
        {
          image: '/images/dump-site-a.jpg',
          title: 'Northern Access Corridor',
          clue: 'Temporary contractor controls at the restricted service approach.',
          reference: 'FIELD-01',
          capturedAt: '07:42 PDT',
        },
        {
          image: '/images/dump-site-b.jpg',
          title: 'Container Staging Record',
          clue: 'Drum inventory documented before transfer to secondary containment.',
          reference: 'FIELD-02',
          capturedAt: '07:51 PDT',
        },
        {
          image: '/images/dump-site-c.jpg',
          title: 'Hazard-Control Posting',
          clue: 'Field notice photographed before the roadside control point was removed.',
          reference: 'FIELD-03',
          capturedAt: '08:03 PDT',
        },
      ],
    });
  }

  @Get('contractor-login')
  contractorLogin(@Res() res: Response) {
    return res.render('contractor-login', {
      title: 'Contractor Incident Access',
      links: [{ text: 'Back to Incident Bulletin', url: '/incident' }],
    });
  }

  @Post('contractor-login')
  contractorLoginPost(
    @Body() body: ContractorLoginDto,
    @Req() req: Request,
    @Res() res: Response,
  ) {
    if (
      !this.challengeService.validateContractorLogin(
        body.username,
        body.password,
      )
    ) {
      this.telemetry.record('contractor.login.failed');
      return res.status(401).render('contractor-login', {
        title: 'Contractor Incident Access',
        error: 'Contractor credentials rejected',
        links: [{ text: 'Back to Incident Bulletin', url: '/incident' }],
      });
    }

    this.session(req).contractorAccess = true;
    this.telemetry.record('contractor.login.succeeded');
    return res.redirect('/contractor');
  }

  @Get('contractor')
  contractor(@Req() req: Request, @Res() res: Response) {
    if (!this.session(req).contractorAccess) {
      return res.redirect('/contractor-login');
    }

    const config = this.challengeService.getConfig();
    return res.render('contractor', {
      title: 'Northline Remediation Dashboard',
      contractorName: config.contractorName,
      facilityName: config.facilityName,
      incidentName: config.incidentName,
      projectCode: config.projectCode,
      fieldPacketCode: config.fieldPacketCode,
      facilityToken: config.facilityCode.split('-')[0].toUpperCase(),
      packetSuffix: config.fieldPacketCode.split('-').at(-1),
      flag: config.flags.phone,
    });
  }

  @Get('challenge-downloads/soil-core-survey.tiff')
  soilCoreSurvey(@Req() req: Request, @Res() res: Response) {
    if (!this.session(req).contractorAccess) {
      return res.redirect('/contractor-login');
    }

    this.telemetry.record('contractor.artifact.downloaded');
    return res.download(
      this.downloadPath('soil-core-survey.tiff'),
      'soil-core-survey.tiff',
    );
  }

  @Get('archive-login')
  archiveLogin(@Res() res: Response) {
    const config = this.challengeService.getConfig();
    return res.render('archive-login', {
      title: 'JANUS Records Exchange',
      projectCode: config.projectCode,
      fieldPacketCode: config.fieldPacketCode,
      facilityName: config.facilityName,
      incidentName: config.incidentName,
      links: [{ text: 'Contractor Dashboard', url: '/contractor' }],
    });
  }

  @Post('archive-login')
  archiveLoginPost(
    @Body() body: ArchiveLoginDto,
    @Req() req: Request,
    @Res() res: Response,
  ) {
    const config = this.challengeService.getConfig();
    if (
      !this.challengeService.validateArchiveLogin(body.username, body.password)
    ) {
      this.telemetry.record('archive.login.failed');
      return res.status(401).render('archive-login', {
        title: 'JANUS Records Exchange',
        projectCode: config.projectCode,
        fieldPacketCode: config.fieldPacketCode,
        facilityName: config.facilityName,
        incidentName: config.incidentName,
        error: 'Archive credentials rejected',
        links: [{ text: 'Contractor Dashboard', url: '/contractor' }],
      });
    }

    this.session(req).archiveAccess = true;
    this.telemetry.record('archive.login.succeeded');
    return res.redirect('/archive');
  }

  @Get('archive')
  archive(@Req() req: Request, @Res() res: Response) {
    if (!this.session(req).archiveAccess) {
      return res.redirect('/archive-login');
    }

    const config = this.challengeService.getConfig();
    res.setHeader('Cache-Control', 'private, no-store');
    res.setHeader('X-JANUS-Namespace', config.facilityCode);
    return res.render('archive', {
      title: 'JANUS Records Vault',
      projectCode: config.projectCode,
      fieldPacketCode: config.fieldPacketCode,
      facilityName: config.facilityName,
      incidentName: config.incidentName,
      flag: config.flags.stego,
    });
  }

  @Get('challenge-downloads/janus-migration-audit.jsonl')
  migrationAudit(@Req() req: Request, @Res() res: Response) {
    if (!this.session(req).archiveAccess) {
      return res.redirect('/archive-login');
    }

    this.telemetry.record('archive.audit.downloaded');
    return res.download(
      this.downloadPath('janus-migration-audit.jsonl'),
      'janus-migration-audit.jsonl',
    );
  }

  @Get('ops/bracken-ridge/mercury-hollow/superadmin')
  superadmin(@Req() req: Request, @Res() res: Response) {
    const config = this.challengeService.getConfig();

    if (!this.session(req).archiveAccess) {
      return res.redirect('/archive-login');
    }

    if (!this.session(req).superadminAccess) {
      return res.render('superadmin-login', {
        title: 'Emergency Operations Control Plane',
        projectCode: config.projectCode,
        fieldPacketCode: config.fieldPacketCode,
        facilityName: config.facilityName,
        incidentName: config.incidentName,
      });
    }

    return res.render('superadmin', {
      title: 'Emergency Operations Control Plane',
      facilityName: config.facilityName,
      incidentName: config.incidentName,
      projectCode: config.projectCode,
      fieldPacketCode: config.fieldPacketCode,
      flag: config.flags.superadmin,
    });
  }

  @Post('ops/bracken-ridge/mercury-hollow/superadmin')
  superadminPost(
    @Body() body: SuperadminLoginDto,
    @Req() req: Request,
    @Res() res: Response,
  ) {
    const config = this.challengeService.getConfig();
    if (!this.session(req).archiveAccess) {
      return res.redirect('/archive-login');
    }

    if (
      !this.challengeService.validateSuperadminLogin(
        body.username,
        body.password,
      )
    ) {
      this.telemetry.record('superadmin.login.failed');
      return res.status(401).render('superadmin-login', {
        title: 'Emergency Operations Control Plane',
        projectCode: config.projectCode,
        fieldPacketCode: config.fieldPacketCode,
        facilityName: config.facilityName,
        incidentName: config.incidentName,
        error: 'Superadmin credentials rejected',
      });
    }

    this.session(req).superadminAccess = true;
    this.telemetry.record('superadmin.login.succeeded');
    return res.redirect(req.path);
  }

  @Get('challenge-downloads/final-remediation-report.pdf')
  finalReport(@Req() req: Request, @Res() res: Response) {
    if (!this.session(req).superadminAccess) {
      return res.redirect('/archive-login');
    }

    this.telemetry.record('final.artifact.downloaded');
    return res.download(
      this.downloadPath('final-remediation-report.pdf'),
      'final-remediation-report.pdf',
    );
  }

  private session(req: Request): ChallengeSession {
    return req.session as ChallengeSession;
  }

  private downloadPath(fileName: string): string {
    return join(process.cwd(), 'public', 'downloads', fileName);
  }
}
