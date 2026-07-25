import 'package:flutter_test/flutter_test.dart';
import 'package:selahcue_controller/models/bible_books.dart';

void main() {
  test('book-name suggestions from a partial token', () {
    expect(suggestBooks('gen'), contains('Genesis'));
    expect(suggestBooks('ps'), contains('Psalms'));
    expect(suggestBooks('rom'), contains('Romans'));
    // Numbered-book abbreviations keep their leading digit.
    expect(suggestBooks('1 co'), contains('1 Corinthians'));
    expect(suggestBooks('2th'), contains('2 Thessalonians'));
    // Full name still matches itself.
    expect(suggestBooks('john'), contains('John'));
  });

  test('no suggestions once a chapter number is typed', () {
    // The book is settled — chips would only get in the way.
    expect(suggestBooks('gen 1'), isEmpty);
    expect(suggestBooks('gen 1 1'), isEmpty);
    expect(suggestBooks('Romans 8:28'), isEmpty);
    expect(suggestBooks(''), isEmpty);
    expect(suggestBooks('   '), isEmpty);
  });

  test('suggestions are bounded', () {
    // A common single letter still returns at most the limit.
    expect(suggestBooks('j', limit: 4).length, lessThanOrEqualTo(4));
  });
}
