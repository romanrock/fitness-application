pipeline {
  agent any
  stages {
    stage('Setup') {
      steps {
        sh 'make setup'
        sh 'make migrate'
      }
    }
    stage('Lint') {
      steps {
        sh 'make lint'
      }
    }
    stage('Test') {
      steps {
        sh 'make test'
      }
    }
    stage('Smoke') {
      steps {
        sh 'python3 scripts/smoke_api.py'
      }
    }
  }
}
