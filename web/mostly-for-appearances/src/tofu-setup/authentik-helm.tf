resource "kubernetes_namespace_v1" "authentik" {
  metadata {
    name = "web-mfa-authentik"
  }
}

resource "helm_release" "authentik" {
  name      = "authentik"
  namespace = kubernetes_namespace_v1.authentik.metadata[0].name

  repository = "https://charts.goauthentik.io"
  chart      = "authentik"

  values = [
    # passwords
    yamlencode({
      authentik = {
        secret_key = random_password.authentik_websecret.result
        # This sends anonymous usage-data, stack traces on errors and
        # performance data to sentry.io, and is fully opt-in
        error_reporting = {
          enabled = false
        }
        postgresql = {
          password = random_password.authentik_db.result
        }
      }

      postgresql = {
        enabled = true
        auth = {
          password = random_password.authentik_db.result
        }
      }
    }),
    # ingress
    yamlencode({
      server = {
        ingress = {
          enabled = true
          annotations = {
            "cert-manager.io/cluster-issuer" = "letsencrypt"
          }
          # Specify kubernetes ingress controller class name
          ingressClassName = "beavercds"
          hosts = [
            "auth.${var.base_domain}",
            # "admin.auth.${var.base_domain}"
          ]
          tls = [
            {
              secretName = "authentik-tls"
              hosts = [
                "auth.${var.base_domain}",
                # "admin.auth.${var.base_domain}"
              ]
            }
          ]
        }
      }
    }),
    # bootstrap creds
    yamlencode({
      authentik = {
        bootstrap_password = random_password.akadmin_user.result
        bootstrap_token    = random_password.akadmin_token.result
      }
    }),
    # resource requests
    yamlencode({
      server = {
        # replicas = 3
        resources = {
          requests = { cpu = "300m", memory = "800Mi" }
          limits   = { cpu = 1, memory = "1.2Gi" }
        }
      }
      worker = {
        # replicas = 2
        resources = {
          requests = { cpu = "400m", memory = "600Mi" }
          limits   = { cpu = 1, memory = "1Gi" }
        }
      }
    }),
  ]
}

# passwords for values
resource "random_password" "authentik_db" {
  length  = 32
  special = false
}
resource "random_password" "akadmin_user" {
  length  = 20
  special = false
}
resource "random_password" "akadmin_token" {
  length  = 20
  special = false
}
resource "random_password" "authentik_websecret" {
  length  = 64
  special = false
}

output "authentik_url" {
  value = "https://auth.${var.base_domain}"
}
output "akadmin_pass" {
  value     = random_password.akadmin_user.result
  sensitive = true
}
