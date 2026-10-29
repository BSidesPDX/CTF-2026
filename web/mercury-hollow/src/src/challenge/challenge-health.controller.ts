import { Controller, Get, Res } from '@nestjs/common';
import type { Response } from 'express';
import { existsSync, statSync } from 'node:fs';
import { join } from 'node:path';

const REQUIRED_ARTIFACTS = [
  'soil-core-survey.tiff',
  'janus-migration-audit.jsonl',
  'final-remediation-report.pdf',
];

@Controller()
export class ChallengeHealthController {
  @Get('health')
  health(@Res({ passthrough: true }) res: Response) {
    const ready = REQUIRED_ARTIFACTS.every((fileName) => {
      const path = join(process.cwd(), 'public', 'downloads', fileName);
      return existsSync(path) && statSync(path).size > 0;
    });

    if (!ready) {
      res.status(503);
    }

    return {
      status: ready ? 'ok' : 'degraded',
      artifactsReady: ready,
    };
  }
}
