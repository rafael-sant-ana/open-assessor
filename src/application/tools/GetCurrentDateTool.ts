import {
    DEFAULT_TIMEZONE,
    todayIn,
    weekdayIn,
    type Clock,
} from '../../domain/dates.js';
import type { Tool } from '../../providers/Tool.js';

export default class GetCurrentDateTool implements Tool {
    readonly name = 'get_current_date';
    readonly description =
        'Returns today\'s date and weekday. Call it before resolving any relative date or period ' +
        '("hoje", "ontem", "sexta passada", "esse mês", "semana passada") for add_expense or list_expenses.';
    readonly parameters = { type: 'object', properties: {} };

    constructor(
        private readonly clock: Clock,
        private readonly timezone: string = DEFAULT_TIMEZONE,
    ) {}

    async execute(): Promise<string> {
        const now = this.clock();
        return JSON.stringify({
            date: todayIn(this.timezone, now),
            weekday: weekdayIn(this.timezone, now),
            timezone: this.timezone,
        });
    }
}
