-- Biome Coaching - PostgreSQL schema
-- Run with: psql -U postgres -d biome_coaching -f schema.sql

-- Enable pgcrypto for gen_random_uuid (if available)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================
-- CORE TABLES
-- ============================================

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  username VARCHAR(100) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  profile_image_url TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_login TIMESTAMP,
  is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS exercises (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) UNIQUE NOT NULL,
  category VARCHAR(50) NOT NULL,
  description TEXT,
  icon VARCHAR(10),
  is_popular BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  exercise_id UUID REFERENCES exercises(id),
  exercise_name VARCHAR(100) NOT NULL,
  video_url TEXT NOT NULL,
  video_duration DECIMAL(10,2),
  file_size BIGINT,
  mime_type VARCHAR(100),
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS analysis_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES analysis_sessions(id) ON DELETE CASCADE,
  overall_score DECIMAL(3,1) NOT NULL,
  total_frames INTEGER NOT NULL,
  processing_time DECIMAL(10,2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS form_issues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  result_id UUID REFERENCES analysis_results(id) ON DELETE CASCADE,
  issue_type VARCHAR(100) NOT NULL,
  severity VARCHAR(20) NOT NULL,
  frame_start INTEGER NOT NULL,
  frame_end INTEGER NOT NULL,
  coaching_cue TEXT NOT NULL,
  confidence_score DECIMAL(3,2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  result_id UUID REFERENCES analysis_results(id) ON DELETE CASCADE,
  metric_name VARCHAR(100) NOT NULL,
  actual_value VARCHAR(50) NOT NULL,
  target_value VARCHAR(50) NOT NULL,
  status VARCHAR(20) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strengths (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  result_id UUID REFERENCES analysis_results(id) ON DELETE CASCADE,
  strength_text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  result_id UUID REFERENCES analysis_results(id) ON DELETE CASCADE,
  recommendation_text TEXT NOT NULL,
  priority INTEGER DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_progress (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  exercise_id UUID REFERENCES exercises(id),
  exercise_name VARCHAR(100) NOT NULL,
  average_score DECIMAL(3,1),
  total_analyses INTEGER DEFAULT 0,
  last_analysis_date TIMESTAMP,
  improvement_trend VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX IF NOT EXISTS idx_analysis_sessions_user_id ON analysis_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_sessions_status ON analysis_sessions(status);
CREATE INDEX IF NOT EXISTS idx_analysis_sessions_created_at ON analysis_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_results_session_id ON analysis_results(session_id);
CREATE INDEX IF NOT EXISTS idx_form_issues_result_id ON form_issues(result_id);
CREATE INDEX IF NOT EXISTS idx_form_issues_severity ON form_issues(severity);
CREATE INDEX IF NOT EXISTS idx_metrics_result_id ON metrics(result_id);
CREATE INDEX IF NOT EXISTS idx_strengths_result_id ON strengths(result_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_result_id ON recommendations(result_id);

-- ============================================
-- SEED DATA
-- ============================================

INSERT INTO exercises (name, category, icon, is_popular) VALUES
  ('Squat', 'Lower Body', '🏋️', true),
  ('Push-up', 'Upper Body', '💪', true),
  ('Deadlift', 'Lower Body', '⚡', true),
  ('Plank', 'Core', '🧘', true),
  ('Lunge', 'Lower Body', '🦵', true),
  ('Pull-up', 'Upper Body', '💪', true),
  ('Bench Press', 'Upper Body', '🏋️', false),
  ('Row', 'Upper Body', '🚣', false),
  ('Overhead Press', 'Upper Body', '🏋️', false),
  ('Hip Thrust', 'Lower Body', '🍑', false)
ON CONFLICT (name) DO NOTHING;


