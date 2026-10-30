variable "project_name" {
  type    = string
  default = "global-career-ai"
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type    = string
  default = "eastus"
}

variable "aks_subnet_id" {
  type = string
}

variable "acr_id" {
  type = string
}

variable "key_vault_id" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "kubernetes_version" {
  type    = string
  default = null
}

variable "node_vm_size" {
  type    = string
  default = "Standard_D4ds_v5"
}

variable "node_min_count" {
  type    = number
  default = 2
}

variable "node_max_count" {
  type    = number
  default = 12
}

variable "pod_cidr" {
  type        = string
  default     = "10.244.0.0/16"
  description = "Non-overlapping pod CIDR for Azure CNI Overlay."
}

variable "service_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "Kubernetes service CIDR; must not overlap VNet or pod CIDRs."
}

variable "dns_service_ip" {
  type        = string
  default     = "10.0.0.10"
  description = "Cluster DNS IP within service_cidr."
}


variable "confidential_node_pool_enabled" {
  type        = bool
  default     = false
  description = "Creates an opt-in confidential-compute node pool. Confirm the VM SKU and confidential runtime support in the deployment region."
}

variable "confidential_node_vm_size" {
  type    = string
  default = "Standard_DC4as_v5"
}

variable "confidential_node_min_count" {
  type    = number
  default = 0
}

variable "confidential_node_max_count" {
  type    = number
  default = 2
}
