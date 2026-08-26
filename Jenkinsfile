// Orchestration definition (Step 7). Documents the scheduled pipeline even if you
// trigger real runs via cron/Makefile instead of running Jenkins locally.
pipeline {
    agent any
    triggers {
        // Daily at 06:00 — incremental pull of new dates only.
        cron('0 6 * * *')
    }
    stages {
        stage('Checkout')           { steps { checkout scm } }
        stage('Build image')        { steps { sh 'docker build -t eu-grid-pulse .' } }
        stage('Run pipeline')       { steps { sh 'docker run --rm --env-file .env eu-grid-pulse' } }
        stage('Publish DQ results') { steps { echo 'TODO: surface dq_results (Step 6)' } }
    }
}
