/* Pure family ordering: completion/priority never separates a child from its parent. */
globalThis.TasklineOrder = {
  families(source) {
    const ids = new Set(source.map(task => task.id));
    return source.filter(task => !ids.has(task.parent_id)).map(parent => ({
      parent,
      children: source.filter(task => task.parent_id === parent.id),
    }));
  },
  group(family) {
    if (family.parent.completed) return 2;
    return [family.parent, ...family.children].some(task => !task.completed && task.starred) ? 0 : 1;
  },
  order(source) {
    return this.families(source)
      .map((family, index) => ({ family, index }))
      .sort((a, b) => this.group(a.family) - this.group(b.family) || a.index - b.index)
      .flatMap(({ family }) => [family.parent, ...family.children]);
  },
  filtered(source, label) {
    return this.families(source).filter(family =>
      [family.parent, ...family.children].some(task => task.label === label)
    ).flatMap(family => [family.parent, ...family.children]);
  },
  reorder(source, ids) {
    const rank = new Map(ids.map((id, index) => [id, index]));
    const families = this.families(source);
    const reordered = [...families];
    for (let group = 0; group <= 2; group += 1) {
      const slots = families.map((family, index) => ({ family, index }))
        .filter(({ family }) => rank.has(family.parent.id) && this.group(family) === group);
      const ordered = slots.map(({ family }) => family)
        .sort((a, b) => rank.get(a.parent.id) - rank.get(b.parent.id));
      slots.forEach(({ index }, offset) => { reordered[index] = ordered[offset]; });
    }
    return reordered.flatMap(family => [family.parent, ...[...family.children].sort((a, b) =>
      (rank.get(a.id) ?? Infinity) - (rank.get(b.id) ?? Infinity)
    )]);
  },
};
