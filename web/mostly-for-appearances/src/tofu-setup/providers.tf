terraform {
  required_version = "~> 1.11" # opentofu
  required_providers {
    random = {
      source = "hashicorp/random"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.1"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.1"
    }
    kubectl = {
      source  = "alekc/kubectl"
      version = "~> 2.2"
    }
    authentik = {
      source  = "goauthentik/authentik"
      version = "~> 2026.8"
    }
  }
}

variable "kube_context" {
  type    = string
  default = "do-sfo3-ctf-mfa"
}
variable "kube_config" {
  type    = string
  default = "../testcluster.kubeconfig"
}

# Kubernetes provider configuration
provider "kubernetes" {
  config_path    = var.kube_config
  config_context = var.kube_context
}

# Helm provider configuration
provider "helm" {
  kubernetes = {
    config_path    = var.kube_config
    config_context = var.kube_context
  }
}

# Kubectl provider configuration
provider "kubectl" {
  config_path    = var.kube_config
  config_context = var.kube_context
}


provider "authentik" {
  url = "https://auth.${var.base_domain}"
  # token    = random_password.akadmin_token.result
  token    = yamldecode(helm_release.authentik.values[2]).authentik.bootstrap_token
  insecure = true # ignore traefik self-signed
}
