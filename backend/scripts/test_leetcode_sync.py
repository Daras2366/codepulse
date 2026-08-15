"""
Test script to validate LeetCode profile synchronization with a real user.

This script:
1. Connects to the database
2. Finds or creates a LeetCode profile for testing
3. Syncs the profile with real LeetCode API data
4. Validates the sync results
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.enums import Platform
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.services.leetcode_sync_service import LeetCodeSyncService


def test_leetcode_sync(username: str = "leetcode"):
    """
    Test LeetCode sync with a real username.
    
    Default username "leetcode" is LeetCode's official account with public data.
    """
    
    print(f"🔍 Testing LeetCode sync for username: {username}")
    print("=" * 60)
    
    # Create database session
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Find or create test user
        test_user = db.query(User).filter(User.username == "leetcode-test-user").first()
        if not test_user:
            print("📝 Creating test user...")
            test_user = User(
                username="leetcode-test-user",
                email="leetcode-test@example.com",
                password_hash="test-hash-for-testing",
            )
            db.add(test_user)
            db.flush()
            print(f"✅ Created test user with ID: {test_user.id}")
        else:
            print(f"✅ Found existing test user with ID: {test_user.id}")
        
        # Find or create LeetCode profile
        profile = db.query(PlatformProfile).filter(
            PlatformProfile.user_id == test_user.id,
            PlatformProfile.platform == Platform.LEETCODE,
            PlatformProfile.username == username,
        ).first()
        
        if not profile:
            print(f"📝 Creating LeetCode profile for {username}...")
            profile = PlatformProfile(
                user_id=test_user.id,
                platform=Platform.LEETCODE,
                username=username,
                current_rating=None,
                max_rating=None,
                rank=None,
                problems_solved=0,
                contests_attended=0,
            )
            db.add(profile)
            db.flush()
            print(f"✅ Created profile with ID: {profile.id}")
        else:
            print(f"✅ Found existing profile with ID: {profile.id}")
        
        # Store pre-sync counts
        pre_problems = db.query(Problem).filter(
            Problem.platform == Platform.LEETCODE
        ).count()
        pre_submissions = db.query(Submission).filter(
            Submission.profile_id == profile.id
        ).count()
        
        print(f"\n📊 Pre-sync state:")
        print(f"   Problems: {pre_problems}")
        print(f"   Submissions: {pre_submissions}")
        print(f"   Profile last synced: {profile.last_synced_at or 'Never'}")
        
        # Perform sync
        print(f"\n🔄 Starting LeetCode sync...")
        service = LeetCodeSyncService(db)
        result = service.sync_leetcode_profile(profile.id, test_user.id)
        
        # Display results
        print(f"\n✅ Sync completed successfully!")
        print(f"\n📈 Sync Results:")
        print(f"   Platform: {result.platform}")
        print(f"   Profile ID: {result.profile_id}")
        print(f"   Problems created: {result.problems_created}")
        print(f"   Submissions created: {result.submissions_created}")
        print(f"   Submissions skipped: {result.submissions_skipped}")
        print(f"   Submissions fetched: {result.submissions_fetched}")
        print(f"   Problems solved: {result.problems_solved}")
        print(f"   Contests attended: {result.contests_attended}")
        print(f"   Synced at: {result.synced_at}")
        
        # Refresh profile
        db.refresh(profile)
        
        # Display updated profile
        print(f"\n👤 Updated Profile:")
        print(f"   Username: {profile.username}")
        print(f"   Current Rating: {profile.current_rating or 'N/A'}")
        print(f"   Max Rating: {profile.max_rating or 'N/A'}")
        print(f"   Rank: {profile.rank or 'N/A'}")
        print(f"   Problems Solved: {profile.problems_solved}")
        print(f"   Contests Attended: {profile.contests_attended}")
        print(f"   Last Synced: {profile.last_synced_at}")
        print(f"   Profile URL: {profile.profile_url or 'N/A'}")
        
        # Verify data integrity
        post_problems = db.query(Problem).filter(
            Problem.platform == Platform.LEETCODE
        ).count()
        post_submissions = db.query(Submission).filter(
            Submission.profile_id == profile.id
        ).count()
        
        print(f"\n📊 Post-sync state:")
        print(f"   Problems: {post_problems} (+{post_problems - pre_problems})")
        print(f"   Submissions: {post_submissions} (+{post_submissions - pre_submissions})")
        
        # Test idempotency - sync again
        print(f"\n🔄 Testing idempotency (second sync)...")
        result2 = service.sync_leetcode_profile(profile.id, test_user.id)
        
        print(f"\n✅ Second sync completed!")
        print(f"   Submissions created: {result2.submissions_created} (should be 0)")
        print(f"   Submissions skipped: {result2.submissions_skipped}")
        print(f"   Problems created: {result2.problems_created} (should be 0)")
        
        if result2.submissions_created == 0 and result2.problems_created == 0:
            print(f"\n✅ Idempotency verified - no duplicates created")
        else:
            print(f"\n⚠️  Warning: Second sync created new records (not idempotent)")
        
        # Show sample submissions
        sample_submissions = db.query(Submission).filter(
            Submission.profile_id == profile.id
        ).order_by(Submission.submitted_at.desc()).limit(5).all()
        
        if sample_submissions:
            print(f"\n📝 Sample submissions (latest 5):")
            for i, sub in enumerate(sample_submissions, 1):
                problem = db.query(Problem).get(sub.problem_id)
                print(f"   {i}. {problem.title} - {sub.status.value} ({sub.language})")
        
        print(f"\n{'=' * 60}")
        print(f"✅ LeetCode sync test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test LeetCode profile synchronization")
    parser.add_argument(
        "username",
        nargs="?",
        default="leetcode",
        help="LeetCode username to sync (default: leetcode)",
    )
    
    args = parser.parse_args()
    
    success = test_leetcode_sync(args.username)
    sys.exit(0 if success else 1)
