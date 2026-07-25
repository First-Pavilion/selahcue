/// Offline scripture book-name autocomplete (Model). The 66 canonical books
/// with common abbreviations, so typing "gen" or "1 co" suggests the full name.
/// Verse resolution still happens host-side over the wire; this is just typing
/// assistance. Mirrors the book set of `selahcue-core::scripture`.
library;

class BibleBook {
  final String name;
  final List<String> aliases;
  const BibleBook(this.name, this.aliases);
}

const List<BibleBook> bibleBooks = [
  BibleBook('Genesis', ['gen', 'ge', 'gn']),
  BibleBook('Exodus', ['exo', 'ex', 'exod']),
  BibleBook('Leviticus', ['lev', 'lv']),
  BibleBook('Numbers', ['num', 'nm', 'nu']),
  BibleBook('Deuteronomy', ['deut', 'dt', 'deu']),
  BibleBook('Joshua', ['josh', 'jos', 'jsh']),
  BibleBook('Judges', ['judg', 'jdg', 'jg']),
  BibleBook('Ruth', ['rth', 'ru']),
  BibleBook('1 Samuel', ['1sam', '1sa', '1s', '1 sam']),
  BibleBook('2 Samuel', ['2sam', '2sa', '2s', '2 sam']),
  BibleBook('1 Kings', ['1kings', '1ki', '1kgs', '1k', '1 ki']),
  BibleBook('2 Kings', ['2kings', '2ki', '2kgs', '2k', '2 ki']),
  BibleBook('1 Chronicles', ['1chron', '1chr', '1ch', '1 chr']),
  BibleBook('2 Chronicles', ['2chron', '2chr', '2ch', '2 chr']),
  BibleBook('Ezra', ['ezr', 'ez']),
  BibleBook('Nehemiah', ['neh', 'ne']),
  BibleBook('Esther', ['esth', 'est', 'es']),
  BibleBook('Job', ['jb']),
  BibleBook('Psalms', ['psalm', 'ps', 'psa', 'pss']),
  BibleBook('Proverbs', ['prov', 'pro', 'prv', 'pr']),
  BibleBook('Ecclesiastes', ['eccl', 'ecc', 'ec']),
  BibleBook('Song of Solomon', ['song', 'sos', 'sng', 'ss']),
  BibleBook('Isaiah', ['isa', 'is']),
  BibleBook('Jeremiah', ['jer', 'je']),
  BibleBook('Lamentations', ['lam', 'la']),
  BibleBook('Ezekiel', ['ezek', 'eze', 'ezk']),
  BibleBook('Daniel', ['dan', 'da', 'dn']),
  BibleBook('Hosea', ['hos', 'ho']),
  BibleBook('Joel', ['joe', 'jl']),
  BibleBook('Amos', ['amo', 'am']),
  BibleBook('Obadiah', ['obad', 'oba', 'ob']),
  BibleBook('Jonah', ['jon', 'jnh']),
  BibleBook('Micah', ['mic', 'mc']),
  BibleBook('Nahum', ['nah', 'na']),
  BibleBook('Habakkuk', ['hab', 'hb']),
  BibleBook('Zephaniah', ['zeph', 'zep', 'zp']),
  BibleBook('Haggai', ['hag', 'hg']),
  BibleBook('Zechariah', ['zech', 'zec', 'zc']),
  BibleBook('Malachi', ['mal', 'ml']),
  BibleBook('Matthew', ['matt', 'mat', 'mt']),
  BibleBook('Mark', ['mrk', 'mk', 'mr']),
  BibleBook('Luke', ['luk', 'lk']),
  BibleBook('John', ['jhn', 'jn', 'joh']),
  BibleBook('Acts', ['act', 'ac']),
  BibleBook('Romans', ['rom', 'ro', 'rm']),
  BibleBook('1 Corinthians', ['1cor', '1co', '1 cor']),
  BibleBook('2 Corinthians', ['2cor', '2co', '2 cor']),
  BibleBook('Galatians', ['gal', 'ga']),
  BibleBook('Ephesians', ['eph', 'ephes']),
  BibleBook('Philippians', ['phil', 'php', 'pp']),
  BibleBook('Colossians', ['col', 'co']),
  BibleBook('1 Thessalonians', ['1thess', '1thes', '1th', '1 th']),
  BibleBook('2 Thessalonians', ['2thess', '2thes', '2th', '2 th']),
  BibleBook('1 Timothy', ['1tim', '1ti', '1 tim']),
  BibleBook('2 Timothy', ['2tim', '2ti', '2 tim']),
  BibleBook('Titus', ['tit', 'ti']),
  BibleBook('Philemon', ['philem', 'phm', 'phlm']),
  BibleBook('Hebrews', ['heb', 'hbr']),
  BibleBook('James', ['jas', 'jm']),
  BibleBook('1 Peter', ['1pet', '1pe', '1pt', '1 pet']),
  BibleBook('2 Peter', ['2pet', '2pe', '2pt', '2 pet']),
  BibleBook('1 John', ['1john', '1jn', '1jo', '1 jn']),
  BibleBook('2 John', ['2john', '2jn', '2jo', '2 jn']),
  BibleBook('3 John', ['3john', '3jn', '3jo', '3 jn']),
  BibleBook('Jude', ['jud', 'jd']),
  BibleBook('Revelation', ['rev', 're', 'rv']),
];

/// The book-name portion the user has typed so far: everything before the first
/// chapter digit (a leading digit for numbered books stays with the book).
/// Returns `(bookToken, rest)` where `rest` is the chapter/verse tail (with its
/// leading space), or `null` if a book already looks fully chosen.
({String book, String rest})? _splitBookToken(String input) {
  final m = RegExp(r'^\s*((?:[1-3]\s*)?[A-Za-z][A-Za-z ]*?)\s*(\d.*)?$')
      .firstMatch(input);
  if (m == null) return null;
  return (book: m.group(1)!.trim(), rest: m.group(2) ?? '');
}

/// Suggest full book names for the current input. Empty once a chapter number
/// has been typed (the book is settled). Matches on normalized name/alias
/// prefix, then substring.
List<String> suggestBooks(String input, {int limit = 6}) {
  final split = _splitBookToken(input);
  if (split == null) return const [];
  // A digit after the book token means the book is chosen — no suggestions.
  if (split.rest.trim().isNotEmpty) return const [];
  final token = split.book.toLowerCase().replaceAll(' ', '');
  if (token.isEmpty) return const [];
  final prefix = <String>[];
  final contains = <String>[];
  for (final b in bibleBooks) {
    final keys = [b.name.toLowerCase().replaceAll(' ', ''), ...b.aliases];
    if (keys.any((k) => k.startsWith(token))) {
      prefix.add(b.name);
    } else if (keys.any((k) => k.contains(token)) ||
        b.name.toLowerCase().contains(split.book.toLowerCase())) {
      contains.add(b.name);
    }
  }
  return [...prefix, ...contains].take(limit).toList();
}
