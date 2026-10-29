resource "authentik_brand" "tangerine" {
  domain  = var.base_domain
  default = false

  branding_title   = "Tangerine Corporate SSO"
  branding_favicon = "https://${var.base_domain}/images/gear.png"
  branding_logo    = "https://${var.base_domain}/images/gear.png"

  flow_authentication = authentik_flow.mfa_login.uuid

  depends_on = [helm_release.authentik, authentik_flow.mfa_login]
}

# User directory

resource "authentik_user" "theresa" {
  name     = "Theresa Barnes"
  username = "barnes.theresa"
  email    = "theresa@tangerineprinting.biz"
  password = random_password.theresa.result
}
resource "random_password" "theresa" {
  length  = 16
  special = true
}

resource "authentik_user" "dylan" {
  name     = "Dylan Jones"
  username = "jones.dylan"
  email    = "dylan@tangerineprinting.biz"
  password = random_password.dylan.result
}
resource "random_password" "dylan" {
  length  = 16
  special = true
}

resource "authentik_user" "alice" {
  name     = "Alice Guerrero"
  username = "guerrero.alice"
  email    = "alice@tangerineprinting.biz"
  password = "alicewonderland2576!" # from post-it
}

# OIDC client for Internal Email (flag-email)

data "authentik_flow" "default_authorization" {
  slug = "default-provider-authorization-implicit-consent"

  depends_on = [helm_release.authentik]
}
data "authentik_flow" "default_invalidation" {
  slug = "default-provider-invalidation-flow"

  depends_on = [helm_release.authentik]
}
data "authentik_certificate_key_pair" "generated" {
  name = "authentik Self-signed Certificate"
}


resource "authentik_provider_oauth2" "flag_email" {
  name               = "Internal Email"
  client_id          = "flag-email"
  authorization_flow = data.authentik_flow.default_authorization.id
  invalidation_flow  = data.authentik_flow.default_invalidation.id
  grant_types        = ["authorization_code", "refresh_token"]

  allowed_redirect_uris = [
    {
      matching_mode     = "strict"
      redirect_uri_type = "authorization"
      url               = "https://webmail.internal.${var.base_domain}/callback"
    },
    {
      matching_mode     = "strict"
      redirect_uri_type = "authorization"
      url               = "http://localhost/callback"
    }
  ]

  # use RS256 signing for JWT token, otherwise Authentik defaults to HS256!
  signing_key = data.authentik_certificate_key_pair.generated.id

  depends_on = [helm_release.authentik]
}

resource "authentik_application" "flag_email" {
  name              = "Internal Email"
  slug              = "internal-email"
  protocol_provider = authentik_provider_oauth2.flag_email.id
  meta_launch_url   = "https://webmail.internal.${var.base_domain}"
}

data "authentik_provider_oauth2_config" "flag_email" {
  name = authentik_provider_oauth2.flag_email.name
}
