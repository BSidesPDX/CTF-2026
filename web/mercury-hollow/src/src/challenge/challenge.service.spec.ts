import manifest from './challenge-manifest.json';
import { ChallengeService } from './challenge.service';

describe('ChallengeService', () => {
  const service = new ChallengeService();

  it('uses the shared challenge manifest', () => {
    expect(service.getConfig()).toEqual(manifest);
  });

  it('validates only exact stage credentials', () => {
    expect(
      service.validateContractorLogin(
        manifest.contractorLogin.username,
        manifest.contractorLogin.password,
      ),
    ).toBe(true);
    expect(
      service.validateArchiveLogin(
        manifest.archiveLogin.username,
        manifest.archiveLogin.password,
      ),
    ).toBe(true);
    expect(
      service.validateSuperadminLogin(
        manifest.superadminLogin.username,
        manifest.superadminLogin.password,
      ),
    ).toBe(true);
    expect(
      service.validateContractorLogin(
        manifest.contractorLogin.username.toUpperCase(),
        manifest.contractorLogin.password,
      ),
    ).toBe(false);
  });
});
