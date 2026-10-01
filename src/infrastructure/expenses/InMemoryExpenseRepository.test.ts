import { expenseRepositoryContract } from './expenseRepositoryContract.js';
import InMemoryExpenseRepository from './InMemoryExpenseRepository.js';

expenseRepositoryContract(
    'InMemoryExpenseRepository',
    () => new InMemoryExpenseRepository(),
);
