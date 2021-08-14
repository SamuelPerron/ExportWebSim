## Installation
1. **Build docker environnment**

    `docker-compose up --build`
2. **Create database** 

    `docker-compose exec db psql -Upostgres -c "CREATE DATABASE tlmhl;"`
3. **Run migrations**

    `docker-compose exec api flask db upgrade`

## Migrations
https://flask-migrate.readthedocs.io/en/latest/index.html

**Creating migrations**

`docker-compose exec api flask db migrate`

**Running migrations**

`docker-compose exec api flask db upgrade`