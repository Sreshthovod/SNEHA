import 'package:flutter/material.dart';

/// Bundled, offline content for activities that do not use the Memory Bank.
/// Labels are English for now; translation drafts need native-speaker review.
class EverydayThing {
  const EverydayThing(this.id, this.label, this.icon, this.category);

  final String id;
  final String label;
  final IconData icon;
  final String category;
}

const everydayCategories = <String, String>{
  'food': 'Food and drink',
  'travel': 'Getting around',
  'home': 'Things at home',
};

const everydayThings = <EverydayThing>[
  EverydayThing('rice', 'Bowl of rice', Icons.rice_bowl, 'food'),
  EverydayThing('tea', 'Cup of tea', Icons.local_cafe, 'food'),
  EverydayThing('egg', 'Egg', Icons.egg, 'food'),
  EverydayThing('fish', 'Fish meal', Icons.set_meal, 'food'),
  EverydayThing('bread', 'Bread', Icons.bakery_dining, 'food'),
  EverydayThing('icecream', 'Ice cream', Icons.icecream, 'food'),
  EverydayThing('bus', 'Bus', Icons.directions_bus, 'travel'),
  EverydayThing('train', 'Train', Icons.train, 'travel'),
  EverydayThing('boat', 'Boat', Icons.directions_boat, 'travel'),
  EverydayThing('bicycle', 'Bicycle', Icons.directions_bike, 'travel'),
  EverydayThing('taxi', 'Taxi', Icons.local_taxi, 'travel'),
  EverydayThing('scooter', 'Scooter', Icons.two_wheeler, 'travel'),
  EverydayThing('chair', 'Chair', Icons.chair, 'home'),
  EverydayThing('bed', 'Bed', Icons.bed, 'home'),
  EverydayThing('bulb', 'Light bulb', Icons.lightbulb, 'home'),
  EverydayThing('door', 'Door', Icons.door_front_door, 'home'),
  EverydayThing('tv', 'Television', Icons.tv, 'home'),
  EverydayThing('umbrella', 'Umbrella', Icons.umbrella, 'home'),
  EverydayThing('watch', 'Watch', Icons.watch, 'home'),
  EverydayThing('key', 'Key', Icons.key, 'home'),
];

class EverydayTask {
  const EverydayTask(this.title, this.steps);

  final String title;

  /// In the correct order.
  final List<String> steps;
}

/// Longest task, so the catalog's highest "steps" level (7) is playable.
const maxTaskSteps = 7;

/// Each task lists its steps in the correct order. Shorter levels use the
/// first N steps, which are always a sensible order on their own.
const everydayTasks = <EverydayTask>[
  EverydayTask('Making tea', [
    'Fill the kettle',
    'Boil the water',
    'Add tea leaves',
    'Let it brew',
    'Add milk and sugar',
    'Stir well',
    'Pour into a cup',
  ]),
  EverydayTask('Getting ready in the morning', [
    'Wake up',
    'Brush your teeth',
    'Wash your face',
    'Have a bath',
    'Put on clean clothes',
    'Comb your hair',
    'Have breakfast',
  ]),
  EverydayTask('Cooking rice', [
    'Measure the rice',
    'Wash the rice',
    'Put the rice in a pot',
    'Add water',
    'Cook on the stove',
    'Let it rest',
    'Serve on a plate',
  ]),
  EverydayTask('Going to the market', [
    'Make a shopping list',
    'Take a bag',
    'Walk to the market',
    'Choose vegetables',
    'Pay the shopkeeper',
    'Carry the bag home',
    'Put things away',
  ]),
];
