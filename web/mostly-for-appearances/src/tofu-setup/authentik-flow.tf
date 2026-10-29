# Custom login flow with our MFA call trigger logic.

resource "authentik_flow" "mfa_login" {
  name        = "ctf-employee-login" # admin ui
  slug        = "employee-login"     # url
  title       = "Employee Login"     # page title
  designation = "authentication"

  policy_engine_mode = "all"
}

# copy most of the default login flow stages
locals {
  existing_stages = {
    "default-authentication-identification" = { order = 10 },
    "default-authentication-password"       = { order = 20 },
    # "default-authentication-mfa-validation" = { order = 30 },
    "default-authentication-login" = { order = 100 },
  }
}
data "authentik_stage" "existing" {
  for_each   = local.existing_stages
  name       = each.key
  depends_on = [helm_release.authentik]
}
resource "authentik_flow_stage_binding" "existing" {
  for_each = local.existing_stages

  target = authentik_flow.mfa_login.uuid
  stage  = data.authentik_stage.existing[each.key].id
  order  = each.value.order

  depends_on = [authentik_flow.mfa_login]
}

#
# now add our own bindings
#

# prompt for phone extension
resource "authentik_stage_prompt" "mfa_confirm_extension" {
  name = "mfa-confirm-extension"
  fields = [
    authentik_stage_prompt_field.mfa_confirm_extension.id,
  ]
  validation_policies = [
    authentik_policy_expression.mfa_trigger_call.id,
  ]
}
resource "authentik_stage_prompt_field" "mfa_confirm_extension" {
  name     = "confirm-extension"
  label    = "Confirm Extension"
  sub_text = "Please confirm your internal phone extension for a verification call."

  type      = "number"
  field_key = "extension"
  required  = true
}
resource "authentik_flow_stage_binding" "mfa_confirm_extension" {
  target = authentik_flow.mfa_login.uuid
  stage  = authentik_stage_prompt.mfa_confirm_extension.id
  order  = 50
}

# Expression policy to trigger the verification call
resource "authentik_policy_expression" "mfa_trigger_call" {
  name              = "mfa-trigger-call"
  execution_logging = true
  expression        = <<-PY
    INSTANCE_MANAGER_SERVICE = "instance-manager.rcds-web-mostly-for-appearances:8080"

    ak_logger.info(f"CONTEXT: {request.context}")
    ext = request.context["prompt_data"]["extension"]
    ak_logger.info(f"triggering call for extension {ext}")

    try:
        info_resp = requests.get(f"http://{INSTANCE_MANAGER_SERVICE}/info?ext={ext}")
        # silently continue on 404, since we should not hint on what extensions
        # are valid or not (instance manager returns 404 if instance for the
        # given extension is not deployed)
        if info_resp.status_code == 404:
            return True

        info_resp.raise_for_status()
        trigger_svc = info_resp.json()["trigger_service"]
    # except requests.exceptions.HTTPError as e:
    except Exception as e:
        ak_message(f"Error triggering call, please try again later!")
        ak_logger.error(f"error getting ext info: {e}")
        return False

    ak_logger.info(f"got trigger service host: {trigger_svc}")

    try:
        resp = requests.post(f"{trigger_svc}/call", data={'extension': ext})
        info_resp.raise_for_status()
    except Exception as e:
        ak_message(f"Error triggering call, please try again later!")
        ak_logger.error(f"error getting ext info: {e}")
        return False

    ak_logger.info(f"got response {resp}")
    ak_message(f"We have called extension {ext} with a verification code.")

    # continue to next stage (mfa prompt) unconditionally
    return True
  PY
}


# then the MFA code prompt

# Custom logic:
#
# resource "authentik_stage_prompt" "mfa_enter_totp" {
#   name = "mfa-enter-totp"
#   fields = [
#     authentik_stage_prompt_field.mfa_enter_totp.id,
#   ]
# }
# resource "authentik_stage_prompt_field" "mfa_enter_totp" {
#   name     = "mfa-enter-totp"
#   label    = "Enter Verification Code"
#   sub_text = "Enter the verification code you received over the phone. This code will be valid for 5 minutes."

#   type      = "text"
#   field_key = "totp"
#   required  = true
# }
# resource "authentik_flow_stage_binding" "mfa_enter_totp" {
#   target = authentik_flow.mfa_login.uuid
#   stage  = authentik_stage_prompt.mfa_enter_totp.id
#   order  = 60
# }

# Built-in MFA autenticator stage:
resource "authentik_stage_authenticator_validate" "mfa_enter_totp" {
  name                  = "mfa-totp-validate"
  device_classes        = ["totp"]
  not_configured_action = "deny"
}
resource "authentik_flow_stage_binding" "mfa_enter_totp" {
  target = authentik_flow.mfa_login.uuid
  stage  = authentik_stage_authenticator_validate.mfa_enter_totp.id
  order  = 60
}



# # bypass MFA stages for akadmin
# resource "authentik_policy_expression" "akadmin_mfa_bypass" {
#   name              = "bypass-mfa-for-akadmin"
#   execution_logging = true
#   expression        = <<-PY
#     return not request.user.username == 'akadmin'
#   PY
# }

# resource "authentik_policy_binding" "akadmin_mfa_bypass_ext" {
#   target = authentik_flow_stage_binding.mfa_confirm_extension.id
#   policy = authentik_policy_expression.akadmin_mfa_bypass.id
#   order  = 0
# }
# resource "authentik_policy_binding" "akadmin_mfa_bypass_totp" {
#   # target = authentik_flow_stage_binding.existing["default-authentication-mfa-validation"].id
#   target = authentik_flow_stage_binding.mfa_enter_totp.id
#   policy = authentik_policy_expression.akadmin_mfa_bypass.id
#   order  = 0
# }
