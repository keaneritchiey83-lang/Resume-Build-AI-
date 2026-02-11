# Deployment Guide

## Prerequisites

- Docker and Docker Compose installed
- Node.js 18+ (for local development)
- PostgreSQL 15+ (if not using Docker)
- Stripe account with API keys
- Domain name (for production)

## Environment Setup

### Backend Environment Variables

Create `backend/.env` from `backend/.env.example`:

```env
NODE_ENV=production
PORT=5000

DATABASE_URL=postgresql://user:password@postgres:5432/resumebuilder

JWT_SECRET=generate-a-secure-random-string-here
JWT_EXPIRES_IN=7d

STRIPE_SECRET_KEY=sk_live_your_live_stripe_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
STRIPE_PRICE_ID_PRO=price_your_pro_plan_id
STRIPE_PRICE_ID_ENTERPRISE=price_your_enterprise_plan_id

CORS_ORIGIN=https://yourdomain.com

RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
```

### Frontend Environment Variables

Create `frontend/.env.production`:

```env
VITE_API_URL=https://api.yourdomain.com
```

## Deployment Options

### Option 1: Docker Compose (Recommended for Single Server)

1. **Clone repository on server**
   ```bash
   git clone https://github.com/keaneritchiey83-lang/Resume-Build-AI-.git
   cd Resume-Build-AI-
   ```

2. **Configure environment variables**
   ```bash
   # Edit backend/.env with production values
   nano backend/.env
   ```

3. **Build and start services**
   ```bash
   docker-compose up -d --build
   ```

4. **Run database migrations**
   ```bash
   docker-compose exec backend npx prisma migrate deploy
   ```

5. **Create admin user** (optional)
   ```bash
   docker-compose exec backend node -e "
   const { PrismaClient } = require('@prisma/client');
   const bcrypt = require('bcryptjs');
   const prisma = new PrismaClient();
   
   async function createAdmin() {
     const password = await bcrypt.hash('admin123', 10);
     await prisma.user.create({
       data: {
         email: 'admin@example.com',
         password,
         firstName: 'Admin',
         role: 'ADMIN',
         subscription: { create: { tier: 'ENTERPRISE' } }
       }
     });
   }
   createAdmin();
   "
   ```

### Option 2: Kubernetes (for Scalability)

1. **Create Kubernetes manifests** (k8s/deployment.yaml, k8s/service.yaml, etc.)

2. **Deploy to cluster**
   ```bash
   kubectl apply -f k8s/
   ```

3. **Set up Ingress for SSL/TLS**

### Option 3: Cloud Platform Specific

#### AWS ECS/Fargate

1. Build and push Docker images to ECR
2. Create ECS task definitions
3. Set up Application Load Balancer
4. Configure RDS for PostgreSQL

#### Google Cloud Run

1. Build images and push to GCR
2. Deploy services with Cloud Run
3. Set up Cloud SQL for PostgreSQL
4. Configure Cloud Load Balancer

#### Heroku

1. Add Heroku Postgres addon
2. Set environment variables
3. Deploy with Git:
   ```bash
   git push heroku main
   ```

## Database Migrations

### Initial Setup
```bash
npx prisma migrate deploy
```

### Future Migrations
```bash
npx prisma migrate dev --name migration_name
npx prisma migrate deploy
```

## SSL/TLS Setup

### Using Let's Encrypt with Nginx

1. **Install Certbot**
   ```bash
   apt-get install certbot python3-certbot-nginx
   ```

2. **Obtain certificate**
   ```bash
   certbot --nginx -d yourdomain.com -d www.yourdomain.com
   ```

3. **Auto-renewal**
   ```bash
   certbot renew --dry-run
   ```

## Stripe Webhook Setup

1. **Go to Stripe Dashboard > Webhooks**

2. **Add endpoint**: `https://api.yourdomain.com/api/subscriptions/webhook`

3. **Select events to listen to**:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`

4. **Copy webhook signing secret** to `STRIPE_WEBHOOK_SECRET`

## Monitoring & Logging

### Application Logs

```bash
# Docker Compose
docker-compose logs -f backend
docker-compose logs -f frontend

# Kubernetes
kubectl logs -f deployment/backend
```

### Health Checks

- Backend: `https://api.yourdomain.com/health`
- Frontend: Access root URL

### Recommended Tools

- **Application Monitoring**: DataDog, New Relic, or Sentry
- **Log Aggregation**: ELK Stack or CloudWatch
- **Uptime Monitoring**: Pingdom or UptimeRobot

## Backup Strategy

### Database Backups

```bash
# Daily backup script
#!/bin/bash
docker-compose exec -T postgres pg_dump -U resumebuilder resumebuilder > backup_$(date +%Y%m%d).sql
```

### Automated Backups

Set up cron job:
```bash
0 2 * * * /path/to/backup.sh
```

## Scaling Considerations

### Horizontal Scaling

1. **Load Balancer**: Use Nginx or cloud load balancer
2. **Multiple Backend Instances**: Scale with Docker replicas or K8s
3. **Database**: Use read replicas for read-heavy workloads
4. **Session Management**: Use Redis for session storage

### Vertical Scaling

- Increase server resources (CPU, RAM)
- Optimize database queries
- Add database indexes

## Security Checklist

- [ ] Use HTTPS everywhere
- [ ] Set secure JWT_SECRET
- [ ] Enable CORS only for your domain
- [ ] Keep dependencies updated
- [ ] Set up firewall rules
- [ ] Use environment variables for secrets
- [ ] Enable rate limiting
- [ ] Regular security audits
- [ ] Database backups configured
- [ ] Monitoring and alerts set up

## Performance Optimization

1. **Enable Gzip compression** in Nginx
2. **CDN for static assets** (CloudFlare, AWS CloudFront)
3. **Database connection pooling** (already configured in Prisma)
4. **Cache frequently accessed data** with Redis
5. **Optimize images** before upload

## Troubleshooting

### Backend won't start

1. Check environment variables
2. Verify database connection
3. Check logs: `docker-compose logs backend`

### Database migration errors

1. Check DATABASE_URL format
2. Ensure database is accessible
3. Try: `npx prisma migrate reset`

### Stripe webhooks not working

1. Verify webhook URL is accessible
2. Check STRIPE_WEBHOOK_SECRET
3. Test with Stripe CLI

## Rollback Procedure

```bash
# Stop current version
docker-compose down

# Checkout previous version
git checkout <previous-commit>

# Rebuild and start
docker-compose up -d --build

# Rollback database if needed
npx prisma migrate resolve --rolled-back <migration-name>
```

## Support

For issues, check:
1. Application logs
2. GitHub Issues
3. Documentation

---

Last updated: 2024