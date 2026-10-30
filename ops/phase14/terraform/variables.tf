variable "management_region" { type = string }
variable "hosted_zone_id" { type = string }
variable "public_fqdn" {
  type = string
  description = "Non-apex DNS hostname (CNAME)"
}
variable "region_a_host" {
  type = string
  description = "Regional ingress DNS, must serve HTTPS /ready"
}
variable "region_b_host" {
  type = string
  description = "Regional ingress DNS, must serve HTTPS /ready"
}
variable "aws_region_a" { type = string }
variable "aws_region_b" { type = string }
variable "monthly_budget_usd" {
  type = string
  validation {
    condition     = can(tonumber(var.monthly_budget_usd)) && tonumber(var.monthly_budget_usd) > 0
    error_message = "monthly_budget_usd must be positive"
  }
}
variable "budget_alert_emails" {
  type = list(string)
  validation {
    condition     = length(var.budget_alert_emails) > 0
    error_message = "provide at least one authorized notification recipient"
  }
}
