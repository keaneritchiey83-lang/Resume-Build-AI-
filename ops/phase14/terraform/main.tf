terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
provider "aws" {
  region = var.management_region
}

# Both regions are ACTIVE. Latency-based DNS routes traffic to healthy regional ingresses.
# These records do not provision the regional clusters, ingress or global database.
resource "aws_route53_health_check" "region_a" {
  fqdn              = var.region_a_host
  port              = 443
  type              = "HTTPS"
  resource_path     = "/ready"
  request_interval  = 30
  failure_threshold = 2
  tags = { Project = "global-career-ai", Region = "a", ManagedBy = "terraform" }
}
resource "aws_route53_health_check" "region_b" {
  fqdn              = var.region_b_host
  port              = 443
  type              = "HTTPS"
  resource_path     = "/ready"
  request_interval  = 30
  failure_threshold = 2
  tags = { Project = "global-career-ai", Region = "b", ManagedBy = "terraform" }
}
resource "aws_route53_record" "global_a" {
  zone_id         = var.hosted_zone_id
  name            = var.public_fqdn
  type            = "CNAME"
  ttl             = 30
  set_identifier  = "active-region-a"
  records         = [var.region_a_host]
  health_check_id = aws_route53_health_check.region_a.id
  latency_routing_policy {
    region = var.aws_region_a
  }
}
resource "aws_route53_record" "global_b" {
  zone_id         = var.hosted_zone_id
  name            = var.public_fqdn
  type            = "CNAME"
  ttl             = 30
  set_identifier  = "active-region-b"
  records         = [var.region_b_host]
  health_check_id = aws_route53_health_check.region_b.id
  latency_routing_policy {
    region = var.aws_region_b
  }
}

resource "aws_budgets_budget" "monthly_account_ceiling" {
  name         = "global-career-ai-phase14-account-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.budget_alert_emails
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.budget_alert_emails
  }
}
