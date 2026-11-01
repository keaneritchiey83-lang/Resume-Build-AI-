variable "project_name" {
  type    = string
  default = "global-career-ai"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "Use at least two private subnets in different availability zones."
  }
}

variable "kubernetes_version" {
  type    = string
  default = "1.34"
}

variable "app_secret_arn" {
  type = string
}

variable "app_kms_key_arn" {
  type = string
}

variable "admin_principal_arn" {
  type = string
}

variable "node_instance_types" {
  type    = list(string)
  default = ["m7i.large", "m6i.large", "m6a.large"]
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_desired_size" {
  type    = number
  default = 3
}

variable "node_max_size" {
  type    = number
  default = 12
}

variable "control_plane_log_retention_days" {
  type    = number
  default = 90
}


variable "confidential_node_group_enabled" {
  type        = bool
  default     = false
  description = "Creates an opt-in Nitro Enclaves-capable node group. Validate instance/AMI/runtime support before enabling."
}

variable "confidential_node_instance_types" {
  type    = list(string)
  default = ["m6i.xlarge"]
}

variable "confidential_node_min_size" {
  type    = number
  default = 0
}

variable "confidential_node_max_size" {
  type    = number
  default = 2
}

variable "credential_signing_kms_arn" {
  type        = string
  default     = ""
  description = "Optional Phase 12 asymmetric KMS signing-key ARN."
}
