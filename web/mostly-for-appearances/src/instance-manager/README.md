This manages the deployment of per-instance 'phone' deployments
and records the service IP for use by the voip admin and authentik call placer.

## Server Configuration

Via envvars:

- `PHONE_DOMAIN=`: parent domain to expose instanced phone uis under (`phone-HASH.`)
- `RESERVED_TTL=`
- `DEPLOYED_TTL=`


## Routes

`GET /available`

Get an available extension id to show to the user and to use later for
deployments. This centralizes the list of available extensions as to not have
conflicting extensions for multiple players. This should reserve the extension
in an internal database (instead of the below POST) to prevent a race condition
of multiple players getting the same ext.

The VOIP phone admin panel will hit this when the user logs in to get the
extension for their session.

If there are no available extensions left, return a 507 error.

`POST /new?ext=12345`

Deploys a new pod and service to the phone namespace, and returns back the
Kubernetes service address for the new service. 
- If the extension was not reserved previously (is available), log a warning
  internally but continue to deploy infra and reserve the extension.
- If the ext is reserved but not deployed, continue and mark as deployed.
- If the ext is deployed already, return 409 Conflict.

The VOIP admin panel will hit this when the users tries to open the reverse
proxy to the phone, and waits for the infra to be deployed before redirecting
the user to the phone site.

`GET /info?ext=12345`

Returns `{ "phone_ui": "http://...", "trigger_service": "http://" }`

Get the Kubernetes service URLs for the phone web ui and call placer service for
this extension. There will be two services deployed as part of each instance:
`phone` for accessing the phone web UI from the voip admin panel, and `trigger` 
for Authentik to trigger a new MFA code call to the instance's phone.

Return 404 if extension is not deployed.

## Behaviour

Extensions are any 5 digit number, chosen randomly. Notionally extensions at a
company this size would be 3 digits, but for player separation reasons we should
use at least 4; 5 will definitely be safe.

When the extension is reserved via `GET /available`, that should mark the
extension as reserved, but only for 1 hour before it is released again. This
will let a player visit the voip admin website and get a number, but not have
to block on deploying the pod until they try to access the phone itself.

Once the player tries to access the phone from the admin panel, the panel will
`POST /new` and actually deploy the instance. This should deploy the manifest to
create resources, and also reserve the extension for a longer period e.g. 8
hours. When this extension expires, the resources for this deployment should be
cleaned up and removed from the cluster.

The deployed infrastructure will be roughly:
- namespace `phone-instance-<12345>` with annotations for deployment status (reserved_at, expires_at, deployed)
- phone instance pod: Asterisk, phone UI, triggerer, SIP answerer, etc.
- phone web UI: exposed as an Ingress with a dynamically generated hash in the domain name
- call trigger service: only as Service in-cluster, not exposed
