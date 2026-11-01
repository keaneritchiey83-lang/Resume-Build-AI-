variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "global-career-ai"
}

variable "api_image" {
  type        = string
  description = "Production API image URI."
}

variable "app_secret_arn" {
  type        = string
  description = "Secrets Manager JSON secret with DATABASE_URL, REDIS_URL, JWT_SECRET, OIDC_SESSION_SECRET, OPENAI_API_KEY and OIDC_CLIENT_SECRET."
}

variable "acm_certificate_arn" {
  type        = string
  description = "ACM certificate ARN for the public HTTPS listener."
}

variable "allowed_ingress_cidrs" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.small"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.small"
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 2
}

variable "deletion_protection" {
  type    = bool
  default = true
}
