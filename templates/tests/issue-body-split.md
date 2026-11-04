<!-- A sample "Onboard an app" issue body for an app split in one repository per component (the whole-app repository left empty); used by the parser test in CI. -->
### App name

split

### GitHub repository

_No response_

### Backend repository

DEVOPS-CANARY/split-backend

### Frontend repository

DEVOPS-CANARY/split-frontend

### Backend

nestjs

### Backend port

3001

### Backend database layer

prisma

### Frontend

nextjs

### Background worker (name)

mailer

### Worker command

node dist/mailer.js

### Package manager

npm

### The app needs

- [x] PostgreSQL
- [ ] Redis
- [x] Kafka

### Owner

@platform-team

### Readiness (platform plan §11)

- [x] Health endpoints for liveness and readiness (A3)
