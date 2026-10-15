import 'activity.dart';
import 'games/everyday_games.dart';
import 'games/memory_games.dart';

/// Slug of the unscored reminiscence activity, which has its own screen
/// (features/memories/story_time_screen.dart) instead of the runner.
const storyTimeSlug = 'story-time';

/// Every playable activity. To add a game, add one entry here.
/// Catalog slugs that are not registered show as "Coming soon".
const Map<String, CognitiveActivity> activityRegistry = {
  'photo-recall': PhotoRecallActivity(),
  'familiar-faces': FamiliarFacesActivity(),
  'picture-pairs': PicturePairsActivity(),
  'daily-sequence': DailySequenceActivity(),
  'name-the-object': NameTheObjectActivity(),
  'sort-into-groups': SortIntoGroupsActivity(),
};
