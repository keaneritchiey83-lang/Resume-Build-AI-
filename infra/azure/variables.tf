variable "location" {
  type    = string
  default = "eastus"
}

variable "project_name" {
  type    = string
  default = "global-career-ai"
}

variable "api_image" {
  type        = string
  description = "API image URI. Push the image to the provisioned ACR before creating Container Apps."
}

variable "postgres_admin_username" {
  type    = string
  default = "careeradmin"
}

variable "postgres_admin_password" {
  type      = string
  sensitive = true
}

variable "postgres_sku_name" {
  type    = string
  default = "GP_Standard_D2ds_v5"
}

variable "managed_redis_sku_name" {
  type    = string
  default = "Balanced_B1"
}

variable "azure_key_name" {
  type    = string
  default = "career-envelope"
}

variable "database_url_secret_id" {
  type        = string
  description = "Versionless Key Vault secret URI containing DATABASE_URL."
}

variable "redis_url_secret_id" {
  type        = string
  description = "Versionless Key Vault secret URI containing REDIS_URL."
}

variable "jwt_secret_id" {
  type        = string
  description = "Versionless Key Vault secret URI containing JWT_SECRET."
}

variable "oidc_session_secret_id" {
  type        = string
  description = "Versionless Key Vault secret URI containing OIDC_SESSION_SECRET."
}

variable "openai_api_key_secret_id" {
  type        = string
  description = "Versionless Key Vault secret URI containing OPENAI_API_KEY."
}

variable "oidc_client_secret_id" {
  type        = string
  description = "Versionless Key Vault secret URI containing OIDC_CLIENT_SECRET."
}
