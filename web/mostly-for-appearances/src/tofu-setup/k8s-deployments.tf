data "kubernetes_namespace_v1" "rcds_web_mfa" {
  metadata {
    name = "rcds-web-mostly-for-appearances"
  }
}



# apache / voip-admin Kubernetes deployment

data "kubectl_file_documents" "apache" {
  content = templatefile("${path.module}/../manifests/apache.manifest.yaml", {
    base_domain = var.base_domain
  })
}

resource "kubectl_manifest" "apache" {
  for_each           = data.kubectl_file_documents.apache.manifests
  yaml_body          = each.value
  override_namespace = data.kubernetes_namespace_v1.rcds_web_mfa.metadata[0].name
}


# instance-manager Kubernetes deployment

data "kubectl_file_documents" "instance_manager" {
  content = templatefile("${path.module}/../manifests/instance-manager.manifest.yaml", {
    base_domain = var.base_domain
  })
}

resource "kubectl_manifest" "instance_manager" {
  for_each           = data.kubectl_file_documents.instance_manager.manifests
  yaml_body          = each.value
  override_namespace = data.kubernetes_namespace_v1.rcds_web_mfa.metadata[0].name
}


# flag-email Kubernetes deployment

resource "random_password" "flag_email_secret_key" {
  length  = 32
  special = false
}

resource "kubernetes_secret_v1" "flag_email" {
  metadata {
    name      = "flag-email-secrets"
    namespace = data.kubernetes_namespace_v1.rcds_web_mfa.metadata[0].name
  }

  data = {
    SECRET_KEY          = random_password.flag_email_secret_key.result
    OAUTH_CLIENT_ID     = authentik_provider_oauth2.flag_email.client_id
    OAUTH_CLIENT_SECRET = authentik_provider_oauth2.flag_email.client_secret
    OAUTH_METADATA_URL  = data.authentik_provider_oauth2_config.flag_email.provider_info_url
  }

  type = "Opaque"
}

data "kubectl_file_documents" "flag_email" {
  content = templatefile("${path.module}/../manifests/flag-email.manifest.yaml", {
    base_domain = var.base_domain
  })
}

resource "kubectl_manifest" "flag_email" {
  for_each           = data.kubectl_file_documents.flag_email.manifests
  yaml_body          = each.value
  override_namespace = data.kubernetes_namespace_v1.rcds_web_mfa.metadata[0].name
  depends_on         = [kubernetes_secret_v1.flag_email]
}



# wildcard TLS certificate Kubernetes secret

data "kubectl_file_documents" "wildcard_tls" {
  content = file("${path.module}/../manifests/wildcard-tls.secret.yaml")
}

resource "kubectl_manifest" "wildcard_tls" {
  for_each           = data.kubectl_file_documents.wildcard_tls.manifests
  yaml_body          = each.value
  override_namespace = data.kubernetes_namespace_v1.rcds_web_mfa.metadata[0].name

  # cert will be replaced with the real one manually
  ignore_fields = ["data.tls.crt", "data.tls.key"]
}
