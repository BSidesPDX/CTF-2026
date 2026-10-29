import { Module } from '@nestjs/common';
import { ChallengeController } from './challenge.controller';
import { ChallengeService } from './challenge.service';
import { ChallengeTelemetryService } from './challenge-telemetry.service';
import { ChallengeHealthController } from './challenge-health.controller';

@Module({
  controllers: [ChallengeController, ChallengeHealthController],
  providers: [ChallengeService, ChallengeTelemetryService],
})
export class ChallengeModule {}
