terraform {
  required_version = ">= 1.7.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
}

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  name = "${var.project_name}-${random_string.suffix.result}"
}

resource "azurerm_resource_group" "main" {
  name     = "${local.name}-rg"
  location = var.location
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.name}-logs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "${local.name}-identity"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_key_vault" "main" {
  name                       = substr(replace("${local.name}-kv", "-", ""), 0, 24)
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "premium"
  purge_protection_enabled   = true
  soft_delete_retention_days = 30
  rbac_authorization_enabled = true
}

resource "azurerm_role_assignment" "deployer_key_crypto" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Crypto Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_key_vault_key" "envelope" {
  name         = var.azure_key_name
  key_vault_id = azurerm_key_vault.main.id
  key_type     = "RSA"
  key_size     = 3072

  key_opts = [
    "unwrapKey",
    "wrapKey",
  ]

  depends_on = [
    azurerm_role_assignment.deployer_key_crypto,
  ]
}

resource "azurerm_role_assignment" "app_key_crypto" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Crypto User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "app_secret_reader" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_virtual_network" "main" {
  name                = "${local.name}-vnet"
  address_space       = ["10.50.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_subnet" "postgres" {
  name                 = "postgres"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.50.1.0/24"]

  delegation {
    name = "postgres"

    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "private-endpoints"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.50.2.0/24"]

  private_endpoint_network_policies = "Disabled"
}

resource "azurerm_subnet" "container_apps" {
  name                 = "container-apps"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.50.4.0/23"]

  delegation {
    name = "container-apps"

    service_delegation {
      name = "Microsoft.App/environments"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

resource "azurerm_private_dns_zone" "postgres" {
  name                = "${local.name}.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
  name                = "${local.name}-postgres-link"
  private_dns_zone_id = azurerm_private_dns_zone.postgres.id
  virtual_network_id  = azurerm_virtual_network.main.id
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${local.name}-postgres"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = "16"
  delegated_subnet_id           = azurerm_subnet.postgres.id
  private_dns_zone_id           = azurerm_private_dns_zone.postgres.id
  administrator_login           = var.postgres_admin_username
  administrator_password        = var.postgres_admin_password
  zone                          = "1"
  storage_mb                    = 65536
  sku_name                      = var.postgres_sku_name
  backup_retention_days         = 14
  geo_redundant_backup_enabled  = false
  public_network_access_enabled = false

  depends_on = [
    azurerm_private_dns_zone_virtual_network_link.postgres,
  ]
}

resource "azurerm_postgresql_flexible_server_database" "career" {
  name      = "career"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "VECTOR"
}

resource "azurerm_managed_redis" "main" {
  name                      = "${local.name}-redis"
  location                  = azurerm_resource_group.main.location
  resource_group_name       = azurerm_resource_group.main.name
  sku_name                  = var.managed_redis_sku_name
  high_availability_enabled = true
  public_network_access     = "Disabled"

  default_database {
    access_keys_authentication_enabled = true
    client_protocol                    = "Encrypted"
    clustering_policy                  = "EnterpriseCluster"
    eviction_policy                    = "VolatileLRU"
  }
}

resource "azurerm_private_dns_zone" "redis" {
  name                = "privatelink.redis.azure.net"
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "redis" {
  name                = "${local.name}-redis-link"
  private_dns_zone_id = azurerm_private_dns_zone.redis.id
  virtual_network_id  = azurerm_virtual_network.main.id
}

resource "azurerm_private_endpoint" "redis" {
  name                = "${local.name}-redis-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "${local.name}-redis-psc"
    private_connection_resource_id = azurerm_managed_redis.main.id
    subresource_names              = ["redisEnterprise"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.redis.id]
  }
}

resource "azurerm_container_registry" "main" {
  name                = substr(replace("${local.name}acr", "-", ""), 0, 50)
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Premium"
  admin_enabled       = false
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_container_app_environment" "main" {
  name                       = "${local.name}-cae"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  infrastructure_subnet_id   = azurerm_subnet.container_apps.id
}

locals {
  app_secret_names = {
    database_url        = var.database_url_secret_id
    redis_url           = var.redis_url_secret_id
    jwt_secret          = var.jwt_secret_id
    oidc_session_secret = var.oidc_session_secret_id
    openai_api_key      = var.openai_api_key_secret_id
    oidc_client_secret  = var.oidc_client_secret_id
  }
}

resource "azurerm_container_app" "api" {
  name                         = "${local.name}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  dynamic "secret" {
    for_each = local.app_secret_names

    content {
      name                = replace(secret.key, "_", "-")
      key_vault_secret_id = secret.value
      identity            = azurerm_user_assigned_identity.app.id
    }
  }

  template {
    min_replicas = 2
    max_replicas = 10

    container {
      name   = "api"
      image  = var.api_image
      cpu    = 1
      memory = "2Gi"

      env {
        name  = "KEY_PROVIDER"
        value = "azure_key_vault"
      }

      env {
        name  = "AZURE_KEY_VAULT_URL"
        value = azurerm_key_vault.main.vault_uri
      }

      env {
        name  = "AZURE_KEY_NAME"
        value = azurerm_key_vault_key.envelope.name
      }

      env {
        name  = "COOKIE_SECURE"
        value = "true"
      }

      env {
        name  = "SCHEDULER_ENABLED"
        value = "true"
      }

      dynamic "env" {
        for_each = local.app_secret_names

        content {
          name        = upper(env.key)
          secret_name = replace(env.key, "_", "-")
        }
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  depends_on = [
    azurerm_role_assignment.app_key_crypto,
    azurerm_role_assignment.app_secret_reader,
    azurerm_role_assignment.acr_pull,
  ]
}

resource "azurerm_container_app" "worker" {
  name                         = "${local.name}-worker"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  dynamic "secret" {
    for_each = local.app_secret_names

    content {
      name                = replace(secret.key, "_", "-")
      key_vault_secret_id = secret.value
      identity            = azurerm_user_assigned_identity.app.id
    }
  }

  template {
    min_replicas = 2
    max_replicas = 10

    container {
      name    = "worker"
      image   = var.api_image
      cpu     = 1
      memory  = "2Gi"
      command = ["celery"]
      args = [
        "-A",
        "app.celery_app.celery",
        "worker",
        "--loglevel=INFO",
        "--concurrency=2",
      ]

      env {
        name  = "KEY_PROVIDER"
        value = "azure_key_vault"
      }

      env {
        name  = "AZURE_KEY_VAULT_URL"
        value = azurerm_key_vault.main.vault_uri
      }

      env {
        name  = "AZURE_KEY_NAME"
        value = azurerm_key_vault_key.envelope.name
      }

      dynamic "env" {
        for_each = local.app_secret_names

        content {
          name        = upper(env.key)
          secret_name = replace(env.key, "_", "-")
        }
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.app_key_crypto,
    azurerm_role_assignment.app_secret_reader,
    azurerm_role_assignment.acr_pull,
  ]
}


resource "azurerm_key_vault_key" "credential_signing" {
  name         = "career-credential-signing"
  key_vault_id = azurerm_key_vault.main.id
  key_type     = "EC-HSM"
  curve        = "P-256"

  key_opts = [
    "sign",
    "verify",
  ]

  depends_on = [
    azurerm_role_assignment.deployer_key_crypto,
  ]
}
